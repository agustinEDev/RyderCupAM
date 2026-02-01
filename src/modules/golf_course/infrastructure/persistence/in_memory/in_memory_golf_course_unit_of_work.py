"""In-Memory Unit of Work para Golf Course Module (testing)."""

from src.modules.golf_course.domain.repositories.golf_course_repository import (
    IGolfCourseRepository,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.infrastructure.persistence.in_memory.in_memory_country_repository import (
    InMemoryCountryRepository,
)

from .in_memory_golf_course_repository import InMemoryGolfCourseRepository


class InMemoryGolfCourseUnitOfWork(GolfCourseUnitOfWorkInterface):
    """
    Implementación en memoria de la Unit of Work para testing del módulo Golf Course.

    Proporciona acceso a repositorios in-memory de:
    - Campos de golf
    - Países (shared)
    """

    def __init__(self):
        self._golf_courses = InMemoryGolfCourseRepository()
        self._countries = InMemoryCountryRepository()
        self.committed = False

    @property
    def golf_courses(self) -> IGolfCourseRepository:
        """Acceso al repositorio de campos de golf."""
        return self._golf_courses

    @property
    def countries(self) -> CountryRepositoryInterface:
        """Acceso al repositorio de países."""
        return self._countries

    async def __aenter__(self):
        """Inicia el contexto async."""
        self.committed = False
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Finaliza el contexto async - maneja commit/rollback automáticamente.

        Comportamiento:
        - Si NO hubo excepción → commit() automático
        - Si hubo excepción → rollback() automático

        Args:
            exc_type: Tipo de excepción (None si no hubo error)
            exc_val: Valor de la excepción
            exc_tb: Traceback de la excepción
        """
        if exc_type:
            # Si hubo excepción, hacer rollback
            await self.rollback()
        else:
            # Si todo fue exitoso, hacer commit automáticamente
            try:
                await self.commit()
            except Exception:
                # Si commit falla, hacer rollback
                await self.rollback()
                raise

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
