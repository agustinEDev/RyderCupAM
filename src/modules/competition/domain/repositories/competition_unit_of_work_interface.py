# -*- coding: utf-8 -*-
"""
Competition Unit of Work Interface - Competition Module Domain Layer.

Define el contrato específico para el Unit of Work del módulo de competiciones.
Esta interfaz extiende la base añadiendo acceso a los repositorios de competiciones.
"""

from abc import abstractmethod
from src.shared.domain.repositories.unit_of_work_interface import UnitOfWorkInterface
from .competition_repository_interface import CompetitionRepositoryInterface
from .enrollment_repository_interface import EnrollmentRepositoryInterface
from src.shared.domain.repositories.country_repository_interface import CountryRepositoryInterface


class CompetitionUnitOfWorkInterface(UnitOfWorkInterface):
    """
    Interfaz específica para el Unit of Work del módulo de competiciones.

    Proporciona acceso coordinado a todos los repositorios relacionados
    con el dominio de competiciones, manteniendo consistencia transaccional.

    Uso típico en casos de uso:
    ```python
    async def create_competition(self, request: CreateCompetitionRequest) -> CompetitionResponse:
        async with self._uow:
            # Verificar que el nombre no existe
            if await self._uow.competitions.exists_with_name(request.name):
                raise CompetitionAlreadyExistsError("Name already used")

            # Crear y guardar competición
            competition = Competition.create(...)
            await self._uow.competitions.save(competition)

            # Commit automático al salir del contexto

        return CompetitionResponse.from_competition(competition)
    ```
    """

    @property
    @abstractmethod
    def competitions(self) -> CompetitionRepositoryInterface:
        """
        Acceso al repositorio de competiciones dentro de la transacción.

        Returns:
            CompetitionRepositoryInterface: Repositorio de competiciones transaccional
        """
        pass

    @property
    @abstractmethod
    def enrollments(self) -> EnrollmentRepositoryInterface:
        """
        Acceso al repositorio de inscripciones dentro de la transacción.

        Returns:
            EnrollmentRepositoryInterface: Repositorio de inscripciones transaccional
        """
        pass

    @property
    @abstractmethod
    def countries(self) -> CountryRepositoryInterface:
        """
        Acceso al repositorio de países dentro de la transacción.

        Necesario para validar países y adyacencias al crear/actualizar competiciones.

        Returns:
            CountryRepositoryInterface: Repositorio de países transaccional
        """
        pass
