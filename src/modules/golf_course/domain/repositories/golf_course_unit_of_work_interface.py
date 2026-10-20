"""
Golf Course Unit of Work Interface - Golf Course Module Domain Layer.

Define el contrato específico para el Unit of Work del módulo de campos de golf.
Esta interfaz extiende la base añadiendo acceso a los repositorios de golf courses.
"""

from abc import abstractmethod

from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.domain.repositories.unit_of_work_interface import UnitOfWorkInterface

from .golf_course_repository import IGolfCourseRepository
from .hole_map_repository import IHoleMapRepository
from .hole_report_repository import IHoleReportRepository
from .hole_sample_repository import IHoleSampleRepository
from .saved_hole_repository import ISavedHoleRepository


class GolfCourseUnitOfWorkInterface(UnitOfWorkInterface):
    """
    Interfaz específica para el Unit of Work del módulo de campos de golf.

    Proporciona acceso coordinado a todos los repositorios relacionados
    con el dominio de campos de golf, manteniendo consistencia transaccional.

    Uso típico en casos de uso:
    ```python
    async def request_golf_course(self, request: RequestGolfCourseRequest) -> GolfCourseResponse:
        async with self._uow:
            # Crear y guardar campo
            golf_course = GolfCourse.create(...)
            await self._uow.golf_courses.save(golf_course)

            # Commit automático al salir del contexto

        return GolfCourseResponse.from_golf_course(golf_course)
    ```
    """

    @property
    @abstractmethod
    def golf_courses(self) -> IGolfCourseRepository:
        """
        Acceso al repositorio de campos de golf dentro de la transacción.

        Returns:
            IGolfCourseRepository: Repositorio de campos transaccional
        """
        pass

    @property
    @abstractmethod
    def countries(self) -> CountryRepositoryInterface:
        """
        Acceso al repositorio de países dentro de la transacción.

        Necesario para validar países al crear/actualizar campos.

        Returns:
            CountryRepositoryInterface: Repositorio de países transaccional
        """
        pass

    @property
    @abstractmethod
    def hole_maps(self) -> IHoleMapRepository:
        """
        Acceso al repositorio de mapas de hoyos dentro de la transacción (BE #532).

        Returns:
            IHoleMapRepository: Repositorio de mapas transaccional
        """
        pass

    @property
    @abstractmethod
    def hole_samples(self) -> IHoleSampleRepository:
        """
        Acceso al repositorio de muestras anónimas de hoyo (BE #532).

        Returns:
            IHoleSampleRepository: Repositorio de muestras transaccional
        """
        pass

    @property
    @abstractmethod
    def hole_reports(self) -> IHoleReportRepository:
        """
        Acceso a los reportes de hoyo de los jugadores (entrega 7, 18 oct 2026).

        Returns:
            IHoleReportRepository: Repositorio de reportes transaccional
        """
        pass

    @property
    @abstractmethod
    def saved_holes(self) -> ISavedHoleRepository:
        """
        Acceso a las líneas que el admin guarda de cada hoyo (BE #575).

        Returns:
            ISavedHoleRepository: Repositorio de líneas guardadas transaccional
        """
        pass
