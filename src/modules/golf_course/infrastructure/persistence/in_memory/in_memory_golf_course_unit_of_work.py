"""In-Memory Unit of Work para Golf Course Module (testing)."""

from src.modules.golf_course.domain.repositories.golf_course_repository import (
    IGolfCourseRepository,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.repositories.hole_map_repository import IHoleMapRepository
from src.modules.golf_course.domain.repositories.hole_report_repository import (
    IHoleReportRepository,
)
from src.modules.golf_course.domain.repositories.hole_sample_repository import (
    IHoleSampleRepository,
)
from src.modules.golf_course.domain.repositories.saved_hole_repository import (
    ISavedHoleRepository,
)
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.infrastructure.persistence.in_memory.in_memory_country_repository import (
    InMemoryCountryRepository,
)

from .in_memory_golf_course_repository import InMemoryGolfCourseRepository
from .in_memory_hole_map_repository import InMemoryHoleMapRepository
from .in_memory_hole_report_repository import InMemoryHoleReportRepository
from .in_memory_hole_sample_repository import InMemoryHoleSampleRepository
from .in_memory_saved_hole_repository import InMemorySavedHoleRepository


class InMemoryGolfCourseUnitOfWork(GolfCourseUnitOfWorkInterface):
    """
    Implementación en memoria de la Unit of Work para testing del módulo Golf Course.

    Proporciona acceso a repositorios in-memory de:
    - Campos de golf
    - Mapas de hoyos
    - Muestras anónimas de hoyo
    - Países (shared)
    """

    def __init__(self):
        self._golf_courses = InMemoryGolfCourseRepository()
        self._hole_maps = InMemoryHoleMapRepository()
        self._hole_samples = InMemoryHoleSampleRepository()
        self._saved_holes = InMemorySavedHoleRepository()
        self._hole_reports = InMemoryHoleReportRepository()
        self._countries = InMemoryCountryRepository()
        self.committed = False

    @property
    def golf_courses(self) -> IGolfCourseRepository:
        """Acceso al repositorio de campos de golf."""
        return self._golf_courses

    @property
    def hole_maps(self) -> IHoleMapRepository:
        """Acceso al repositorio de mapas de hoyos."""
        return self._hole_maps

    @property
    def hole_samples(self) -> IHoleSampleRepository:
        """Acceso al repositorio de muestras de hoyo."""
        return self._hole_samples

    @property
    def saved_holes(self) -> ISavedHoleRepository:
        """Acceso a las líneas guardadas de los hoyos."""
        return self._saved_holes

    @property
    def hole_reports(self) -> IHoleReportRepository:
        """Acceso a los reportes de hoyo."""
        return self._hole_reports

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
