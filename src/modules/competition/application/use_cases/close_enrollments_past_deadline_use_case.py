"""
Caso de Uso: Cerrar las inscripciones a las que ya les pasó el plazo (15 nov 2026).

Lo lanza un proceso cada hora, no una petición. El plazo son las 12:00 del día
anterior al torneo, a la hora del campo; desde ahí nadie entra aunque siga
ACTIVE (C2), y esta vuelta la pasa a CLOSED con el MISMO caso de uso que cierra
a mano (C3): refresco con la RFEG, hándicaps y categorías fijados, quien solo
esperaba sale, las invitaciones pendientes se quedan sin plaza. El organizador
recibe «se han cerrado las inscripciones de X» (C5).

Un Stableford o un Medal con aprobados sin franja o sin hándicap no se puede
cerrar: sigue ACTIVE —el plazo ya no deja entrar a nadie— y al organizador se
le dice UNA vez, no cada hora (C4). Cada vuelta lo vuelve a intentar.

Cada competición se cierra en su propia transacción. Un fallo en una no para
las demás.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta

from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CloseBlockedReason,
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.services.franjas_al_cerrar import (
    PlayersWithoutTeeWindowError,
)
from src.modules.competition.application.services.handicaps_al_cerrar import (
    PlayersWithoutHandicapError,
)
from src.modules.competition.application.services.plazo_de_inscripcion import (
    PlazoDeInscripcion,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.domain.policies.enrollment_deadline import en_utc
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus

logger = logging.getLogger(__name__)

# El plazo son las 12:00 del día anterior; en la zona más adelantada (UTC+14)
# eso son las 22:00 UTC de dos días antes. Lo que empieza más tarde no ha podido
# pasar su plazo en ninguna zona, y ni se lee
DIAS_QUE_SE_MIRAN = 2
# Y hacia atrás, un mes: lo que no se cerró a su hora es una exenta (R1, R2) o
# un stroke play bloqueado (C4). Pasado un mes del torneo ya no hay nada que
# cerrar, y así la vuelta no crece con el tiempo (F6, 16 nov 2026)
DIAS_HACIA_ATRAS = 30


@dataclass(frozen=True)
class ClosedByDeadline:
    """Lo que hizo una vuelta."""

    closed: int = 0
    blocked: int = 0
    notified: int = 0
    failed: int = 0


class CloseEnrollmentsPastDeadlineUseCase:
    """Cierra las inscripciones abiertas cuyo plazo ya pasó."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        cerrar: CloseEnrollmentsUseCase,
        plazo: PlazoDeInscripcion,
        actividad: CompetitionActivityPublisherInterface | None = None,
        fallos_conocidos: set[CompetitionId] | None = None,
    ):
        """
        Args:
            uow: Para leer las candidatas y apuntar el aviso de C4
            cerrar: El cierre de siempre, con el plazo (C3)
            plazo: La zona del campo y el reloj
            actividad: Para el aviso de que no se pueden cerrar (C4). Sin él no
                se avisa, y por eso tampoco se apunta
            fallos_conocidos: Las que ya fallaron en otra vuelta de este
                proceso: su traza ya está en el registro (F4)
        """
        self._uow = uow
        self._cerrar = cerrar
        self._plazo = plazo
        self._publicador = actividad
        self._fallos = fallos_conocidos if fallos_conocidos is not None else set()

    async def execute(self) -> ClosedByDeadline:
        ahora = self._plazo.ahora()
        hoy = en_utc(ahora).date()
        desde = hoy - timedelta(days=DIAS_HACIA_ATRAS)
        hasta = hoy + timedelta(days=DIAS_QUE_SE_MIRAN)
        async with self._uow:
            # Antes que nada, las que abrió la release anterior sin apuntar cuándo:
            # se les apunta ahora, y así ninguna se cierra de golpe (D3)
            for sin_fecha in await self._uow.competitions.find_active_without_opening_time():
                if sin_fecha.record_unknown_opening(ahora):
                    await self._uow.competitions.update(sin_fecha)
        async with self._uow:
            # Los ids y no las entidades: el rollback de una que falla caduca
            # todo lo cargado en la sesión
            candidatas = [
                c.id for c in await self._uow.competitions.find_active_starting_by(desde, hasta)
            ]
        # Lo que ya no es candidata (cerrada, cancelada, fuera de la ventana) no
        # vuelve a fallar: se olvida, y así el conjunto no crece (D6)
        self._fallos.intersection_update(candidatas)

        closed = blocked = notified = failed = 0
        for competition_id in candidatas:
            # Todo lo de cada una dentro de su frontera de errores, también apuntar
            # el aviso de bloqueo: si algo falla, se apunta y se sigue con las
            # demás (CodeRabbit, #865). Lo deshace cada transacción al salir con el
            # error (`async with` de la unidad de trabajo): aquí ya no queda nada
            try:
                cerrada, bloqueada, avisada = await self._una(competition_id)
            except Exception:
                self._fallo(competition_id)
                failed += 1
                continue
            self._fallos.discard(competition_id)
            closed += cerrada
            blocked += bloqueada
            notified += avisada
        return ClosedByDeadline(closed, blocked, notified, failed)

    async def _una(self, competition_id: CompetitionId) -> tuple[int, int, int]:
        """
        La cierra, o avisa de que no se puede.

        Returns:
            (cerrada, bloqueada, avisada), cada uno 0 o 1
        """
        try:
            cerrada = await self._cerrar.cerrar_por_el_plazo(competition_id)
        except PlayersWithoutTeeWindowError as error:
            motivo, jugadores = CloseBlockedReason.NO_TEE_WINDOW, len(error.players)
        except PlayersWithoutHandicapError as error:
            motivo, jugadores = CloseBlockedReason.NO_HANDICAP, len(error.players)
        else:
            return (1 if cerrada is not None else 0), 0, 0
        return 0, 1, await self._avisar_bloqueada(competition_id, motivo, jugadores)

    def _fallo(self, competition_id: CompetitionId) -> None:
        """
        La traza, la primera vez que falla en este proceso, como ERROR para que
        llegue a Sentry (D2); después, en DEBUG: se reintenta cada hora y repetir
        el error cada hora no dice nada nuevo (F4). Tras un reinicio, otra vez una.
        """
        if competition_id in self._fallos:
            logger.debug("Still cannot close the enrollments of %s", competition_id, exc_info=True)
            return
        self._fallos.add(competition_id)
        logger.exception(
            "Could not close the enrollments of %s; will retry every hour", competition_id
        )

    async def _avisar_bloqueada(
        self, competition_id: CompetitionId, motivo: CloseBlockedReason, jugadores: int
    ) -> int:
        """
        Una vez por competición, decidido, publicado y apuntado con la fila
        bloqueada (D4): un cierre a mano a la vez espera, y al cerrar ve el apunte
        y retira el aviso. Si publicar falla no se apunta, y la vuelta siguiente
        lo intenta otra vez (C4, F3). Devuelve 1 si avisó.
        """
        if self._publicador is None:
            return 0
        async with self._uow:
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)
            if (
                competition is None
                or competition.status is not CompetitionStatus.ACTIVE
                or competition.close_blocked_notified
                # Con la fila ya bloqueada, otra vez: el organizador ha podido
                # moverla entre medias, y entonces ya no le toca (CodeRabbit, #865)
                or not await self._plazo.le_toca_cerrarse(competition)
            ):
                return 0
            try:
                await self._publicador.close_blocked(competition, motivo, jugadores)
            except Exception:
                logger.warning(
                    "Could not tell the organizer that %s cannot be closed",
                    competition_id,
                    exc_info=True,
                )
                return 0
            competition.mark_close_blocked_notified()
            await self._uow.competitions.update(competition)
        return 1
