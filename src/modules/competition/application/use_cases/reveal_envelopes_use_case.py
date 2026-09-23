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


class RivalEnvelopeMissingError(Exception):
    """Un capitan no puede abrir mientras el rival no haya entregado."""

    pass


class RevealEnvelopesUseCase:
    """Caso de uso para abrir los dos sobres de una sesion."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface, user_repository):
        """
        Args:
            uow: Unit of Work del modulo
            user_repository: De donde sale el handicap para el sobre que falte
        """
        self._uow = uow
        self._desk = EnvelopeDesk(uow, user_repository)

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
            RivalEnvelopeMissingError: Si los abre un capitan y el rival no ha
                entregado todavia
            EnvelopeAlreadyRevealedError: Si ya estaban abiertos
        """
        async with self._uow:
            ronda, competition = await self._desk.ronda_y_competicion(
                RoundId(round_id), bloquear=True
            )
            es_capitan = self._desk.equipo_de(competition, user_id) is not None
            arbitra = is_admin or competition.is_creator(user_id)
            if not arbitra and not es_capitan:
                raise NotCompetitionCreatorError(
                    "Los sobres los abre el organizador o uno de los capitanes"
                )
            if not arbitra:
                # Un capitan no puede forzar que el rival se rellene solo: el
                # relleno automatico es PREDECIBLE —por handicap—, asi que
                # entregar y abrir de inmediato deja armar la lista propia para
                # ganar todos los cruces. El azar de esto esta en no saber que
                # hizo el otro. El organizador si puede: es quien arbitra, y si
                # un capitan no aparece no se queda todo parado
                await self._comprobar_que_los_dos_entregaron(ronda)

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

    async def _comprobar_que_los_dos_entregaron(self, ronda) -> None:
        """Los dos sobres tienen que estar dentro.

        Raises:
            RivalEnvelopeMissingError: Si falta alguno
        """
        entregados = {
            sobre.team
            for sobre in await self._uow.envelopes.find_by_round(ronda.id)
            if sobre.is_submitted()
        }
        if entregados != {"A", "B"}:
            raise RivalEnvelopeMissingError(
                "El otro capitán todavía no ha entregado su sobre: los abre el organizador"
            )
