"""
Caso de Uso: Abrir los sobres de una sesion (FE #655).

Se abren los dos a la vez y salen los enfrentamientos, cruzando las dos listas
por posicion. **El sobre que no llego lo rellena la aplicacion** —por handicap,
juntando al mejor con el peor en los formatos de dos— y **no pisa al capitan
que si entrego**: el que llego a tiempo no se queda sin su lista por culpa del
que se olvido (decidido el 20 sep).
"""

from datetime import UTC, datetime
from uuid import UUID

from src.modules.competition.application.dto.envelope_dto import RevealEnvelopesResponseDTO
from src.modules.competition.application.exceptions import NotCompetitionCreatorError
from src.modules.competition.application.services.envelope_desk import EnvelopeDesk
from src.modules.competition.application.use_cases.get_envelopes_use_case import _cruzados
from src.modules.competition.domain.entities.envelope import EnvelopeAlreadyRevealedError
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class RevealEnvelopesUseCase:
    """Caso de uso para abrir los dos sobres de una sesion."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Args:
            uow: Unit of Work del modulo
        """
        self._uow = uow
        self._desk = EnvelopeDesk(uow)

    async def execute(
        self, round_id: UUID, user_id: UserId, is_admin: bool = False
    ) -> RevealEnvelopesResponseDTO:
        """
        Abre los dos sobres y devuelve los enfrentamientos.

        Args:
            round_id: La sesion
            user_id: Quien los abre: el organizador o uno de los capitanes
            is_admin: Si es administrador

        Returns:
            Los enfrentamientos y que equipos llevaban sobre automatico

        Raises:
            RoundNotFoundError: Si la sesion no existe
            NotCompetitionCreatorError: Si no es el organizador ni un capitan
            EnvelopeAlreadyRevealedError: Si ya estaban abiertos
        """
        async with self._uow:
            ronda, competition = await self._desk.ronda_y_competicion(RoundId(round_id))
            es_capitan = self._desk.equipo_de(competition, user_id) is not None
            if not is_admin and not competition.is_creator(user_id) and not es_capitan:
                raise NotCompetitionCreatorError(
                    "Los sobres los abre el organizador o uno de los capitanes"
                )

            ahora = datetime.now(UTC).replace(tzinfo=None)
            automaticos = []
            sobres = {}
            for team in ("A", "B"):
                sobre = await self._desk.sobre_de(ronda, team, crear=True)
                if not sobre.is_sealed():
                    raise EnvelopeAlreadyRevealedError("Los sobres de esta sesión ya se abrieron")
                if not sobre.is_submitted():
                    jugadores = await self._desk.jugadores_de(competition, team)
                    sobre.fill(await self._desk.handicaps_de(competition, jugadores), ahora=ahora)
                    automaticos.append(team)
                sobre.reveal()
                await self._uow.envelopes.update(sobre)
                sobres[team] = sobre

            return RevealEnvelopesResponseDTO(
                round_id=ronda.id.value,
                matchups=_cruzados(sobres["A"], sobres["B"]),
                filled_automatically=automaticos,
            )
