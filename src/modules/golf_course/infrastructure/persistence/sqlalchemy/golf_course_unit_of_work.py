"""
SQLAlchemy Unit of Work - Golf Course Module Infrastructure Layer.

Implementación asíncrona del Unit of Work para el módulo de campos de golf.
Coordina transacciones entre 2 repositorios: golf_courses, countries.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.golf_course.domain.repositories.golf_course_repository import (
    IGolfCourseRepository,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.infrastructure.persistence.repositories.golf_course_repository import (
    GolfCourseRepository,
)
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.infrastructure.persistence.sqlalchemy.country_repository import (
    SQLAlchemyCountryRepository,
)


class SQLAlchemyGolfCourseUnitOfWork(GolfCourseUnitOfWorkInterface):
    """
    Implementación asíncrona de la Unit of Work con SQLAlchemy para Golf Course Module.

    Características:
    - Gestiona transacciones atómicas para múltiples repositorios
    - Context manager con commit/rollback automático
    - Patrón AsyncContextManager (__aenter__ / __aexit__)
    - Integración con Domain Events (preparado para publicación futura)

    Uso típico:
    ```python
    async with uow:
        # Validar país
        country = await uow.countries.find_by_code(country_code)

        # Crear campo
        golf_course = GolfCourse.create(...)
        await uow.golf_courses.save(golf_course)

        # Commit automático al salir
    # Rollback automático si hay excepción
    ```
    """

    def __init__(self, session: AsyncSession):
        """
        Constructor.

        Args:
            session: Sesión asíncrona de SQLAlchemy compartida por todos los repositorios
        """
        self._session = session
        # Inicializar los 2 repositorios con la misma sesión (transacción compartida)
        self._golf_courses = GolfCourseRepository(session)
        self._countries = SQLAlchemyCountryRepository(session)

    @property
    def golf_courses(self) -> IGolfCourseRepository:
        """
        Repositorio de campos de golf.

        Returns:
            IGolfCourseRepository: Repositorio transaccional
        """
        return self._golf_courses

    @property
    def countries(self) -> CountryRepositoryInterface:
        """
        Repositorio de países (shared domain).

        Necesario para validar países al crear campos.

        Returns:
            CountryRepositoryInterface: Repositorio transaccional
        """
        return self._countries

    async def __aenter__(self):
        """
        Context manager entry - inicia el contexto transaccional.

        Returns:
            Self para uso en 'async with' statement
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit - maneja commit/rollback automáticamente.

        Clean Architecture: El Use Case NO debe manejar transacciones explícitamente.
        El UoW se encarga automáticamente de persistir cambios y publicar eventos.

        Comportamiento:
        - Si NO hubo excepción → commit() automático + publicar domain events
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

                # Domain Events: Los eventos están registrados en las entidades
                # Nota: Para MVP, los eventos están listos pero la publicación
                # real a un event bus se implementará cuando se necesiten handlers
                # (ej: enviar emails, actualizar vistas materializadas, etc.)
            except Exception:
                # Si commit falla, hacer rollback para limpiar estado de transacción
                await self.rollback()
                raise  # Re-raise para que el caller vea el error

    async def commit(self) -> None:
        """
        Confirma la transacción actual, persistiendo todos los cambios.

        Este método es llamado automáticamente por __aexit__ si no hubo errores.
        También puede ser llamado explícitamente desde use cases si se necesita
        commit parcial (ej: flush intermedio para obtener IDs generados).
        """
        await self._session.commit()

    async def rollback(self) -> None:
        """
        Revierte la transacción actual, descartando todos los cambios.

        Este método es llamado automáticamente por __aexit__ si hubo una excepción.
        También puede ser llamado explícitamente desde use cases si se detecta
        un error de negocio que requiere rollback manual.
        """
        await self._session.rollback()

    async def flush(self) -> None:
        """
        Sincroniza cambios con la BD sin hacer commit.

        Útil para:
        - Obtener IDs generados por la BD sin commitear
        - Forzar validaciones de constraints antes del commit final
        - Tests que necesitan verificar estado intermedio

        Nota: Los cambios son visibles dentro de la transacción pero NO se
        confirman hasta que se llame a commit().
        """
        await self._session.flush()

    def is_active(self) -> bool:
        """
        Verifica si la sesión de BD está activa.

        Returns:
            bool: True si la sesión está activa, False en caso contrario
        """
        return self._session.is_active
