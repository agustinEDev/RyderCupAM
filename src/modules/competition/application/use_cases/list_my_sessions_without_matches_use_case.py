"""
Caso de Uso: Las sesiones de mis competiciones que se quedaron sin partidos (BE #361).

Los partidos se crean al abrirse los sobres. Cuando no se pueden crear —a un
jugador le falta el género, el campo no tiene su color de barras— la sesion se
queda con los enfrentamientos a la vista y sin partidos, y eso lo tiene que
arreglar el organizador. Esto es lo que alimenta su aviso en «Requiere tu
atencion»: sin el, se enteraria a la hora de jugar.
"""

from src.modules.competition.application.dto.match_generation_block_dto import (
    SessionWithoutMatchesDTO,
    block_to_dto,
)
from src.modules.competition.application.services.envelope_desk import ORDEN_DE_SESION
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_status import SE_JUEGA
from src.modules.user.domain.value_objects.user_id import UserId

# Un organizador con mucho historial no puede perder el aviso por el corte por
# defecto del repositorio, que son 100
_TODAS_LAS_SUYAS = 1000


class ListMySessionsWithoutMatchesUseCase:
    """Caso de uso para listar las sesiones bloqueadas de un organizador."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Args:
            uow: Unit of Work del modulo
        """
        self._uow = uow

    async def execute(self, user_id: UserId) -> list[SessionWithoutMatchesDTO]:
        """
        Devuelve las sesiones de sus competiciones que esperan partidos y no
        los pudieron tener.

        Args:
            user_id: Quien pregunta. Solo ve las competiciones que organiza

        Returns:
            Una por sesion, de la mas proxima a la mas lejana. Vacio casi siempre
        """
        async with self._uow:
            sesiones: list[SessionWithoutMatchesDTO] = []
            for competition in await self._uow.competitions.find_by_creator(
                user_id, limit=_TODAS_LAS_SUYAS
            ):
                # De una terminada o cancelada no queda nada que arreglar
                if competition.status not in SE_JUEGA:
                    continue
                for ronda in await self._uow.rounds.find_by_competition(competition.id):
                    # Generarlos a mano o rehacer los sobres borra el motivo, asi
                    # que el que sigue apuntado es de una sesion sin partidos
                    motivo = ronda.match_generation_block
                    if motivo is None:
                        continue
                    dto = block_to_dto(motivo)
                    sesiones.append(
                        SessionWithoutMatchesDTO(
                            round_id=ronda.id.value,
                            competition_id=competition.id.value,
                            competition_name=str(competition.name),
                            round_date=ronda.round_date,
                            session_type=ronda.session_type.value,
                            reason=dto.reason,
                            players=dto.players,
                        )
                    )
            return sorted(
                sesiones,
                key=lambda s: (s.round_date, _ORDEN.get(s.session_type, 0)),
            )


_ORDEN = {tipo.value: orden for tipo, orden in ORDEN_DE_SESION.items()}
