"""
Reabrir las inscripciones, en un solo sitio (15 nov 2026).

Lo hace el organizador con su botón, y también mover el torneo cuando lo había
cerrado el plazo y el plazo nuevo está en el futuro (R3). Los dos tienen que
hacer lo mismo: la entidad vuelve a ACTIVE (y olvida el reparto de categorías),
la actualización de hándicaps a medias se corta, las partidas que no han
salido se borran, con sus avisos de salida retirados, y las invitaciones que
esperaban vuelven a pendientes, con su «ya puedes aceptar» (P2).
"""

from collections.abc import Callable
from datetime import datetime

from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.actualizaciones_de_handicaps import (
    ActualizacionesDeHandicaps,
)
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.invitaciones_al_cerrar import (
    vuelven_las_que_esperan,
)
from src.modules.competition.application.services.partidas_del_jugador import (
    salidas_por_hora,
)
from src.modules.competition.application.services.salidas_de_la_ronda import (
    Salidas,
    de_las_partidas,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class Reapertura:
    """Reabre una competición cerrada, con todo lo que eso arrastra."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone | None,
        reloj: Callable[[], datetime],
        actividad: AvisosDeActividad,
    ):
        """
        Args:
            zonas: Para no borrar las partidas que ya salieron por su hora (#251).
                Sin ellas, solo cuenta el estado de la partida
            actividad: Para retirar los avisos de salida de las partidas que se
                borran (G4)
        """
        self._uow = uow
        self._zonas = zonas
        self._reloj = reloj
        self._actividad = actividad
        # Los aprobados al reabrir: sus avisos de hándicaps con la RFEG se retiran
        self._inscritos: list[UserId] = []
        # Las invitaciones que esperaban y vuelven, para avisar ya guardado (P2)
        self._vuelven: list[Invitation] = []

    async def reabrir(self, competition: Competition) -> dict[RoundId, Salidas]:
        """
        Dentro de la transacción de quien llama, con la competición bloqueada.

        Returns:
            Por franja, las salidas de las partidas borradas: para `avisar`

        Raises:
            CompetitionStateError: Si no está cerrada
        """
        # Con la hora: reabierta pasado el plazo, ya no se cierra sola (R1)
        competition.reopen_enrollments(now=self._reloj())

        # La actualización de hándicaps que esté a medias se corta: al volver
        # a cerrar empieza otra (#251)
        await ActualizacionesDeHandicaps(self._uow, None).cortar(competition.id)

        # Las invitaciones que esperaban vuelven a pendientes (P2, 15 nov 2026)
        self._vuelven = await vuelven_las_que_esperan(self._uow, competition.id)

        # Las partidas que no han salido se borran: pueden entrar y salir
        # jugadores, y se vuelven a generar al cerrar. Las que salieron (por su
        # estado o por su hora: hasta la PR 5 nadie las pasa a IN_PROGRESS) se
        # quedan: lo jugado no se borra (D1, #251)
        borradas = await self._borrar_las_que_no_salieron(competition.id)

        # Sus avisos de hándicaps con la RFEG dejan de ser ciertos (CodeRabbit, #864)
        self._inscritos = [
            i.user_id
            for i in await self._uow.enrollments.find_by_competition_and_status(
                competition.id, EnrollmentStatus.APPROVED
            )
        ]
        return borradas

    async def avisar(self, competition: Competition, borradas: dict[RoundId, Salidas]) -> None:
        """
        Ya guardada: sin partida no hay salida, y se retiran sus avisos (G4); y
        los de hándicaps con la RFEG, que dejan de ser ciertos (#864); y a cada
        invitado que esperaba, «ya puedes aceptar» (P2).
        """
        for round_id, salidas in borradas.items():
            await self._actividad.salidas_cambiadas(competition, round_id, salidas, {})
        await self.avisar_handicaps(competition)
        await self.avisar_a_los_invitados(competition)

    async def avisar_handicaps(self, competition: Competition) -> None:
        """Los avisos de hándicaps con la RFEG de la competición reabierta se retiran (#864)."""
        await self._actividad.handicaps_not_updated_withdrawn(competition)
        await self._actividad.handicap_not_found_withdrawn(competition, self._inscritos)

    async def avisar_a_los_invitados(self, competition: Competition) -> None:
        """Ya guardada: a cada invitado que esperaba, «ya puedes aceptar» (P2)."""
        await self._actividad.invitations_acceptable_again(competition, self._vuelven)

    async def _borrar_las_que_no_salieron(
        self, competition_id: CompetitionId
    ) -> dict[RoundId, Salidas]:
        """
        Returns:
            Por franja, las salidas de los jugadores de las partidas borradas
        """
        partidas = await self._uow.partidas.de_la_competicion(competition_id)
        ahora = self._reloj()
        salidas: set[PartidaId] = set()
        franjas: dict[RoundId, Round] = {}
        for round_id in {p.round_id for p in partidas}:
            franja = await self._uow.rounds.find_by_id(round_id)
            if franja is not None:
                franjas[round_id] = franja
                de_la_franja = [p for p in partidas if p.round_id == round_id]
                salidas |= await salidas_por_hora(franja, de_la_franja, self._zonas, ahora)
        borrar = [p for p in partidas if not p.empezada and p.id not in salidas]
        await self._uow.partidas.borrar(borrar)
        return {
            round_id: de_las_partidas(franja, [p for p in borrar if p.round_id == round_id])
            for round_id, franja in franjas.items()
            if any(p.round_id == round_id for p in borrar)
        }
