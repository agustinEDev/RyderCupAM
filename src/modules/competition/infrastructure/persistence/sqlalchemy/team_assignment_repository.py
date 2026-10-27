"""TeamAssignment Repository - SQLAlchemy Implementation."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.repositories.team_assignment_repository_interface import (
    TeamAssignmentRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.team_assignment_id import (
    TeamAssignmentId,
)
from src.shared.infrastructure.persistence.leidos_en_la_sesion import (
    lista_leida,
    olvidar_listas,
    recordar_lista,
)

# El reparto de cada competición ya leído en la petición (o que no lo hay)
_REPARTO = "reparto_de"


class SQLAlchemyTeamAssignmentRepository(TeamAssignmentRepositoryInterface):
    """Implementacion asincrona del repositorio de asignaciones con SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, assignment: TeamAssignment) -> None:
        self._session.add(assignment)
        olvidar_listas(self._session, _REPARTO)

    async def find_by_id(self, assignment_id: TeamAssignmentId) -> TeamAssignment | None:
        return await self._session.get(TeamAssignment, assignment_id)

    async def find_by_competition(self, competition_id: CompetitionId) -> TeamAssignment | None:
        # Una vez por petición: la ficha de una Ryder lo pedía hasta tres veces
        # (hay equipos, cómo se repartieron, si está publicada). También que no
        # lo hay, que es lo habitual hasta formarlos (PR 2 de rendimiento)
        if (ya := lista_leida(self._session, (_REPARTO, competition_id))) is not None:
            return ya[0] if ya else None
        statement = (
            select(TeamAssignment)
            .where(TeamAssignment._competition_id == competition_id)
            .order_by(TeamAssignment._created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(statement)
        reparto = result.scalar_one_or_none()
        recordar_lista(self._session, (_REPARTO, competition_id), [reparto] if reparto else [])
        return reparto

    async def delete(self, assignment_id: TeamAssignmentId) -> bool:
        assignment = await self.find_by_id(assignment_id)
        if assignment is None:
            return False
        await self._session.delete(assignment)
        olvidar_listas(self._session, _REPARTO)
        return True
