"""
Caso de Uso: Rehacer los sobres de una sesion (FE #655).

Cuando un capitan no llega a tiempo, la aplicacion rellena su sobre y salen los
enfrentamientos. Lo que viene despues **no es editar el resultado: es rehacer el
proceso**, y solo puede pedirlo el organizador: es quien arbitra, y el capitan
que si entrego a tiempo no se queda sin su lista por culpa del que se olvido.

Se lleva los sobres Y los partidos de esa sesion. Dejar los partidos seria
dejarlos diciendo un orden de juego que ya no sale de ningun sobre, que es justo
lo que los sobres vienen a decidir.
"""

from uuid import UUID

from src.modules.competition.application.dto.envelope_dto import ResetEnvelopesResponseDTO
from src.modules.competition.application.exceptions import NotCompetitionCreatorError
from src.modules.competition.application.services.envelope_desk import EnvelopeDesk
from src.modules.competition.application.services.lo_jugado import LoJugado
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.user.domain.value_objects.user_id import UserId


class SessionAlreadyPlayedError(Exception):
    """Esa sesion ya se jugo: rehacerla se llevaria lo anotado."""

    pass


class NothingToResetError(Exception):
    """No hay sobres ni partidos que rehacer."""

    pass


class ResetEnvelopesUseCase:
    """Caso de uso para rehacer los sobres de una sesion."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface, user_repository):
        """
        Args:
            uow: Unit of Work del modulo
            user_repository: Lo pide la mesa de sobres
        """
        self._uow = uow
        self._desk = EnvelopeDesk(uow, user_repository)

    async def execute(
        self, round_id: UUID, user_id: UserId, is_admin: bool = False
    ) -> ResetEnvelopesResponseDTO:
        """
        Tira los sobres y los partidos de la sesion para empezar de nuevo.

        Args:
            round_id: La sesion
            user_id: Quien lo pide: el organizador o un administrador
            is_admin: Si es administrador

        Returns:
            Cuantos sobres y cuantos partidos se han ido

        Raises:
            RoundNotFoundError: Si la sesion no existe
            NotCompetitionCreatorError: Si no es el organizador ni administrador
            SessionAlreadyPlayedError: Si ya se jugo algo de esa sesion
            NothingToResetError: Si no hay sobres ni partidos
        """
        async with self._uow:
            ronda, competition = await self._desk.ronda_y_competicion(
                RoundId(round_id), bloquear=True
            )
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError(
                    "Rehacer los sobres es cosa del organizador: es quien arbitra"
                )

            sobres = await self._uow.envelopes.find_by_round(ronda.id)
            # Con la fila bloqueada: entre preguntar y borrar cabe un golpe, y
            # anotar no bloquea la competicion (la misma razon que el borrado)
            partidos = await self._uow.matches.find_by_round_for_update(ronda.id)
            if not sobres and not partidos:
                raise NothingToResetError(
                    "Esta sesión no tiene sobres ni partidos: no hay nada que rehacer"
                )

            if await LoJugado(self._uow).en_la_sesion(ronda.id, bloquear=True):
                raise SessionAlreadyPlayedError(
                    "No se pueden rehacer los sobres de una sesión que ya se ha jugado: "
                    "se irían con ellos los partidos y lo anotado"
                )

            for partido in partidos:
                await self._uow.matches.delete(partido.id)
            await self._uow.envelopes.delete_by_round(ronda.id)

            # La sesion vuelve a esperar sus partidos, que es de donde salio.
            # Sin esto se queda sin un solo partido en un estado que «generar»
            # rechaza, y no habria forma de rehacerla. Tambien desde
            # IN_PROGRESS: una sesion arranca sola a su hora (BE #305) sin que
            # nadie haya jugado, y hasta aqui solo llega lo NO jugado
            if ronda.status in (RoundStatus.SCHEDULED, RoundStatus.IN_PROGRESS):
                ronda.reset_to_pending_matches()
                await self._uow.rounds.update(ronda)

            await self._uow.commit()
            return ResetEnvelopesResponseDTO(
                round_id=ronda.id.value,
                envelopes_removed=len(sobres),
                matches_removed=len(partidos),
            )
