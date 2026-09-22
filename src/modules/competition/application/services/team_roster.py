"""
TeamRoster - Quién sigue en cada equipo, para elegir capitán o subcapitán.

El reparto (`TeamAssignment`) guarda las dos listas tal como quedaron, y una
baja no las toca. Para elegir a alguien «de su equipo» cuentan los que están en
esa lista Y siguen inscritos y aprobados: quien se retiró ya no puede ser
capitán ni subcapitán (BE #320).
"""

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.user.domain.value_objects.user_id import UserId


class TeamRoster:
    """Los jugadores que siguen en un equipo ya repartido."""

    @staticmethod
    async def de_un_equipo(
        uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId, team: str
    ) -> tuple[list[UserId], bool]:
        """
        Los jugadores de ese equipo que siguen inscritos, y si hay reparto.

        Args:
            uow: Unit of Work ya abierta
            competition_id: La competición
            team: "A" o "B" (la entidad valida el valor)

        Returns:
            (jugadores del equipo aprobados, si hay equipos repartidos)
        """
        reparto = await uow.team_assignments.find_by_competition(competition_id)
        if reparto is None:
            return [], False
        aprobados = {
            e.user_id
            for e in await uow.enrollments.find_by_competition_and_status(
                competition_id, EnrollmentStatus.APPROVED
            )
        }
        lista = reparto.team_a_player_ids if team == "A" else reparto.team_b_player_ids
        return [j for j in lista if j in aprobados], True
