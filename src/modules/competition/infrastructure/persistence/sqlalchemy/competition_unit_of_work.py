"""
SQLAlchemy Unit of Work - Competition Module Infrastructure Layer.

Implementacion asincrona del Unit of Work para el modulo de competiciones.
Coordina transacciones entre 8 repositorios.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.competition.domain.repositories.competition_repository_interface import (
    CompetitionRepositoryInterface,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.repositories.enrollment_repository_interface import (
    EnrollmentRepositoryInterface,
)
from src.modules.competition.domain.repositories.hole_score_repository_interface import (
    HoleScoreRepositoryInterface,
)
from src.modules.competition.domain.repositories.invitation_repository_interface import (
    InvitationRepositoryInterface,
)
from src.modules.competition.domain.repositories.match_repository_interface import (
    MatchRepositoryInterface,
)
from src.modules.competition.domain.repositories.round_repository_interface import (
    RoundRepositoryInterface,
)
from src.modules.competition.domain.repositories.team_assignment_repository_interface import (
    TeamAssignmentRepositoryInterface,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.enrollment_repository import (
    SQLAlchemyEnrollmentRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.hole_score_repository import (
    SQLAlchemyHoleScoreRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.invitation_repository import (
    SQLAlchemyInvitationRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.match_repository import (
    SQLAlchemyMatchRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.round_repository import (
    SQLAlchemyRoundRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.team_assignment_repository import (
    SQLAlchemyTeamAssignmentRepository,
)
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.infrastructure.persistence.sqlalchemy.country_repository import (
    SQLAlchemyCountryRepository,
)


class SQLAlchemyCompetitionUnitOfWork(CompetitionUnitOfWorkInterface):
    """
    Implementacion asincrona de la Unit of Work con SQLAlchemy para Competition Module.

    Gestiona transacciones atomicas para todos los repositorios del modulo.
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._competitions = SQLAlchemyCompetitionRepository(session)
        self._enrollments = SQLAlchemyEnrollmentRepository(session)
        self._countries = SQLAlchemyCountryRepository(session)
        self._rounds = SQLAlchemyRoundRepository(session)
        self._matches = SQLAlchemyMatchRepository(session)
        self._team_assignments = SQLAlchemyTeamAssignmentRepository(session)
        self._invitations = SQLAlchemyInvitationRepository(session)
        self._hole_scores = SQLAlchemyHoleScoreRepository(session)

    @property
    def competitions(self) -> CompetitionRepositoryInterface:
        return self._competitions

    @property
    def enrollments(self) -> EnrollmentRepositoryInterface:
        return self._enrollments

    @property
    def countries(self) -> CountryRepositoryInterface:
        return self._countries

    @property
    def rounds(self) -> RoundRepositoryInterface:
        return self._rounds

    @property
    def matches(self) -> MatchRepositoryInterface:
        return self._matches

    @property
    def team_assignments(self) -> TeamAssignmentRepositoryInterface:
        return self._team_assignments

    @property
    def invitations(self) -> InvitationRepositoryInterface:
        return self._invitations

    @property
    def hole_scores(self) -> HoleScoreRepositoryInterface:
        return self._hole_scores

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            await self.commit()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def flush(self) -> None:
        await self._session.flush()

    def is_active(self) -> bool:
        return self._session.is_active
