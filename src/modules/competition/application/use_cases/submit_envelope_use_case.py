"""
Caso de Uso: Entregar el sobre de un capitan (FE #655).

Cada capitan entrega una lista ORDENADA de los suyos sin ver la del otro, y los
enfrentamientos salen de cruzar las dos por posicion. Se puede corregir hasta
que se abren; despues no, que seria rehacer el sorteo a escondidas.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from src.modules.competition.application.dto.envelope_dto import EnvelopeDTO
from src.modules.competition.application.services.envelope_desk import EnvelopeDesk
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class NotATeamCaptainError(Exception):
    """Solo los capitanes entregan sobre."""

    pass


class SubmitEnvelopeUseCase:
    """Caso de uso para entregar —o corregir— el sobre de un equipo."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface, user_repository):
        """
        Args:
            uow: Unit of Work del modulo
            user_repository: Lo pide la mesa de sobres para los handicaps
        """
        self._uow = uow
        self._desk = EnvelopeDesk(uow, user_repository)

    async def execute(
        self, round_id: UUID, user_id: UserId, entries: Sequence[Sequence[str | UUID]]
    ) -> EnvelopeDTO:
        """
        Guarda la lista del capitan para esa sesion.

        Args:
            round_id: La sesion
            user_id: Quien entrega. De aqui sale el equipo: pedirlo en el
                cuerpo dejaria entregar el sobre del rival
            entries: Las filas, en orden

        Returns:
            El sobre tal como queda

        Raises:
            RoundNotFoundError: Si la sesion no existe
            NotATeamCaptainError: Si quien entrega no capitanea ningun equipo
            EnvelopeAlreadyRevealedError: Si ya se abrio
            PlayerNotInTeamError: Si alguien no es de su equipo
            TeamNotFullyEnteredError: Si falta alguien del equipo
        """
        async with self._uow:
            # Con la competicion bloqueada: dos peticiones a la vez leerian
            # que no hay sobre, las dos lo crearian, y una reventaria contra la
            # clave unica con un 500
            ronda, competition = await self._desk.ronda_y_competicion(
                RoundId(round_id), bloquear=True
            )
            team = self._desk.equipo_de(competition, user_id)
            if team is None:
                raise NotATeamCaptainError("Solo los capitanes entregan su sobre")

            sobre = await self._desk.sobre_de(ronda, team, crear=True)
            jugadores = await self._desk.jugadores_de(competition, team)
            sobre.submit(
                [[UserId(UUID(str(uid))) for uid in fila] for fila in entries],
                equipo=jugadores,
                por=user_id,
                ahora=datetime.now(UTC).replace(tzinfo=None),
            )
            await self._uow.envelopes.update(sobre)
            return _a_dto(sobre)


def _a_dto(sobre) -> EnvelopeDTO:
    """El sobre tal como lo ve quien puede verlo."""
    return EnvelopeDTO(
        round_id=sobre.round_id.value,
        team=sobre.team,
        entries=[[uid.value for uid in fila] for fila in sobre.entries],
        submitted=sobre.is_submitted(),
        submitted_at=sobre.submitted_at,
        automatic=sobre.automatic,
    )
