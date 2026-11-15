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
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
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
    ):
        """
        Args:
            uow: Para leer las candidatas y apuntar el aviso de C4
            cerrar: El cierre de siempre, con el plazo (C3)
            plazo: La zona del campo y el reloj
            actividad: Para el aviso de que no se pueden cerrar (C4)
        """
        self._uow = uow
        self._cerrar = cerrar
        self._plazo = plazo
        self._actividad = AvisosDeActividad(actividad)

    async def execute(self) -> ClosedByDeadline:
        hasta = en_utc(self._plazo.ahora()).date() + timedelta(days=DIAS_QUE_SE_MIRAN)
        async with self._uow:
            # Los ids y no las entidades: el rollback de una que falla caduca
            # todo lo cargado en la sesión
            candidatas = [c.id for c in await self._uow.competitions.find_active_starting_by(hasta)]

        closed = blocked = notified = failed = 0
        for competition_id in candidatas:
            try:
                cerrada = await self._cerrar.cerrar_por_el_plazo(competition_id)
            except PlayersWithoutTeeWindowError as error:
                blocked += 1
                notified += await self._avisar_bloqueada(
                    competition_id, CloseBlockedReason.NO_TEE_WINDOW, len(error.players)
                )
                continue
            except PlayersWithoutHandicapError as error:
                blocked += 1
                notified += await self._avisar_bloqueada(
                    competition_id, CloseBlockedReason.NO_HANDICAP, len(error.players)
                )
                continue
            except Exception:
                logger.exception("Could not close the enrollments of %s", competition_id)
                failed += 1
                continue
            if cerrada is not None:
                closed += 1
        return ClosedByDeadline(closed, blocked, notified, failed)

    async def _avisar_bloqueada(
        self, competition_id: CompetitionId, motivo: CloseBlockedReason, jugadores: int
    ) -> int:
        """
        Una vez por competición: se apunta con la fila bloqueada, y solo si sigue
        abierta (C4). Devuelve 1 si avisó.
        """
        async with self._uow:
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)
            if (
                competition is None
                or competition.status is not CompetitionStatus.ACTIVE
                or competition.close_blocked_notified
            ):
                return 0
            competition.mark_close_blocked_notified()
            await self._uow.competitions.update(competition)
        await self._actividad.close_blocked(competition, motivo, jugadores)
        return 1
