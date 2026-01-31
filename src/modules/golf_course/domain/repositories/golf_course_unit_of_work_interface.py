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
