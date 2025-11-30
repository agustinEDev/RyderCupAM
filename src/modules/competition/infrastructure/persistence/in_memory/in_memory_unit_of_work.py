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
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.infrastructure.persistence.in_memory.in_memory_country_repository import (
    InMemoryCountryRepository,
)

from .in_memory_competition_repository import InMemoryCompetitionRepository
from .in_memory_enrollment_repository import InMemoryEnrollmentRepository


class InMemoryUnitOfWork(CompetitionUnitOfWorkInterface):
    """
    Implementación en memoria de la Unit of Work para testing del módulo Competition.

    Proporciona acceso a repositorios in-memory de:
    - Competiciones
    - Inscripciones
    - Países (shared)
    """

    def __init__(self):
        self._competitions = InMemoryCompetitionRepository()
        self._enrollments = InMemoryEnrollmentRepository()
        self._countries = InMemoryCountryRepository()
        self.committed = False

    @property
    def competitions(self) -> CompetitionRepositoryInterface:
        """Acceso al repositorio de competiciones."""
        return self._competitions

    @property
    def enrollments(self) -> EnrollmentRepositoryInterface:
        """Acceso al repositorio de inscripciones."""
        return self._enrollments

    @property
    def countries(self) -> CountryRepositoryInterface:
        """Acceso al repositorio de países."""
        return self._countries

    async def __aenter__(self):
        """Inicia el contexto async."""
        self.committed = False
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Finaliza el contexto async."""
        pass

    async def commit(self) -> None:
        """Confirma la transacción."""
        self.committed = True

    async def rollback(self) -> None:
        """Revierte la transacción."""
        self.committed = False

    async def flush(self) -> None:
        """En memoria, flush no tiene efecto real."""
        pass

    def is_active(self) -> bool:
        """La transacción siempre se considera activa en memoria."""
        return True
