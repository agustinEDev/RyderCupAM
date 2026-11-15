"""
Qué marca el cupo de una competición (release social 3, 28 oct 2026).

Sin franjas, el máximo de jugadores. En un stroke play con franjas, las plazas
de sus franjas: quien solo espera no ocupa sitio, y el máximo deja de mirarse
en TODOS los caminos de entrar —apuntarse, invitar, aceptar, aprobar, a mano—,
también para cerrar las invitaciones pendientes «sin plaza» (decidido con
Agustín tras el revisor de la BE PR A).
"""

from src.modules.competition.application.services.invitaciones_al_cerrar import (
    al_ocupar_una_plaza,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.competition_policy import CompetitionPolicy


async def manda_el_maximo(uow: CompetitionUnitOfWorkInterface, competition: Competition) -> bool:
    """Si el cupo es `max_players`: sí, salvo que tenga franjas montadas."""
    sesiones = await uow.rounds.find_by_competition(competition.id)
    return not any(s.hoja_de_salidas is not None for s in sesiones)


async def exigir_sitio(uow: CompetitionUnitOfWorkInterface, competition: Competition) -> int:
    """
    Las aprobadas ahora; y, si manda el máximo, que quede sitio.

    Raises:
        CompetitionFullViolation: Si manda el máximo y está lleno
    """
    aprobadas = await uow.enrollments.count_approved_by_competition(competition.id)
    if await manda_el_maximo(uow, competition):
        CompetitionPolicy.validate_capacity(aprobadas, competition.max_players, competition.id)
    return aprobadas


async def al_entrar_uno(
    uow: CompetitionUnitOfWorkInterface, competition: Competition, aprobadas_antes: int
) -> list[Invitation]:
    """Si con él se llena el máximo, las pendientes se quedan sin plaza (BE #359); con
    franjas, nunca por ese número."""
    if not await manda_el_maximo(uow, competition):
        return []
    return await al_ocupar_una_plaza(uow, competition.id, aprobadas_antes, competition.max_players)
