"""In-Memory Unit of Work para Competition Module (testing)."""

from src.modules.competition.domain.repositories.competition_repository_interface import (
    CompetitionRepositoryInterface,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.repositories.enrollment_repository_interface import (
    EnrollmentRepositoryInterface,
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
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.infrastructure.persistence.in_memory.in_memory_country_repository import (
    InMemoryCountryRepository,
)

from .in_memory_competition_repository import InMemoryCompetitionRepository
from .in_memory_enrollment_repository import InMemoryEnrollmentRepository
from .in_memory_match_repository import InMemoryMatchRepository
from .in_memory_round_repository import InMemoryRoundRepository
from .in_memory_team_assignment_repository import InMemoryTeamAssignmentRepository


class InMemoryUnitOfWork(CompetitionUnitOfWorkInterface):
    """Implementacion en memoria de la Unit of Work para testing."""

    def __init__(self):
        self._competitions = InMemoryCompetitionRepository()
        self._enrollments = InMemoryEnrollmentRepository()
        self._countries = InMemoryCountryRepository()
        self._rounds = InMemoryRoundRepository()
        self._matches = InMemoryMatchRepository()
        self._team_assignments = InMemoryTeamAssignmentRepository()
        self.committed = False

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

    async def __aenter__(self):
        self.committed = False
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            try:
                await self.commit()
            except Exception:
                await self.rollback()
                raise

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.committed = False

    async def flush(self) -> None:
        pass

    def is_active(self) -> bool:
        return True
