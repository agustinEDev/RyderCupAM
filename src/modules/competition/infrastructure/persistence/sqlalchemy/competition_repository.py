"""
Competition Repository - SQLAlchemy Implementation.

Implementación concreta del repositorio de competiciones usando SQLAlchemy async.
"""

from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.competition_golf_course import (
    CompetitionGolfCourse,
)
from src.modules.competition.domain.repositories.competition_repository_interface import (
    CompetitionRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import (
    CompetitionName,
)
from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyCompetitionRepository(CompetitionRepositoryInterface):
    """
    Implementación asíncrona del repositorio de competiciones con SQLAlchemy.

    Sigue el patrón Repository establecido en el módulo User.
    Maneja la persistencia de la entidad Competition usando async/await.
    """

    def __init__(self, session: AsyncSession):
        """
        Constructor del repositorio.

        Args:
            session: Sesión asíncrona de SQLAlchemy
        """
        self._session = session

    async def add(self, competition: Competition) -> None:
        """
        Agrega una nueva competición al repositorio.

        SQLAlchemy marcará el objeto para INSERT en el próximo flush/commit.

        Args:
            competition: Entidad Competition a guardar

        Note:
            El commit se maneja en el Unit of Work, no aquí.
        """
        self._session.add(competition)

    async def update(self, competition: Competition) -> None:
        """
        Actualiza una competición existente.

        SQLAlchemy detecta automáticamente los cambios en objetos trackeados.
        Si el objeto no está en la sesión, lo mergeamos.

        Args:
            competition: Entidad Competition con datos actualizados
        """
        self._session.add(competition)

    async def delete(self, competition_id: CompetitionId) -> bool:
        """
        Elimina una competición físicamente del repositorio.

        Args:
            competition_id: ID de la competición a eliminar

        Returns:
            bool: True si se eliminó, False si no existía
        """
        competition = await self.find_by_id(competition_id)
        if competition:
            await self._session.delete(competition)
            return True
        return False

    async def find_by_id(self, competition_id: CompetitionId) -> Competition | None:
        """
        Busca una competición por su ID único.

        Eager loads the golf_courses relationship and nested golf_course entities.

        Args:
            competition_id: ID de la competición

        Returns:
            Optional[Competition]: La competición encontrada o None
        """
        stmt = (
            select(Competition)
            .where(Competition.id == competition_id)
            .options(
                selectinload(Competition._golf_courses)
                .selectinload(CompetitionGolfCourse.golf_course)
                .options(
                    selectinload(GolfCourse._tees),
                    selectinload(GolfCourse._holes),
                )
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_id_for_update(self, competition_id: CompetitionId) -> Competition | None:
        """
        Busca una competición por su ID con bloqueo de fila (SELECT ... FOR UPDATE).

        Args:
            competition_id: ID de la competición

        Returns:
            Optional[Competition]: La competición encontrada o None
        """
        stmt = select(Competition).where(Competition.id == competition_id).with_for_update()
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_creator(
        self, creator_id: UserId, limit: int = 100, offset: int = 0
    ) -> list[Competition]:
        """
        Busca todas las competiciones creadas por un usuario.

        Args:
            creator_id: ID del usuario creador
            limit: Número máximo de resultados (paginación)
            offset: Número de resultados a saltar (paginación)

        Returns:
            List[Competition]: Lista de competiciones del creador
        """
        statement = (
            select(Competition)
            .where(Competition.creator_id == creator_id)
            .order_by(Competition.created_at.desc())  # Más recientes primero
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_by_status(
        self, status: CompetitionStatus, limit: int = 100, offset: int = 0
    ) -> list[Competition]:
        """
        Busca todas las competiciones con un estado específico.

        Args:
            status: Estado de la competición (enum)
            limit: Número máximo de resultados
            offset: Número de resultados a saltar

        Returns:
            List[Competition]: Lista de competiciones con el estado especificado

        Note:
            Usamos el atributo privado _status_value porque status es un composite.
        """
        statement = (
            select(Competition)
            .where(Competition._status_value == status.value)
            .order_by(Competition.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_active_in_date_range(
        self, start_date: date, end_date: date
    ) -> list[Competition]:
        """
        Busca competiciones activas que se superpongan con un rango de fechas.

        La query busca competiciones donde:
        - Status sea ACTIVE, CLOSED, IN_PROGRESS (estados "activos")
        - Las fechas se superpongan con el rango dado

        Solapamiento de rangos:
        - comp.start_date <= end_date AND comp.end_date >= start_date

        Args:
            start_date: Fecha de inicio del rango
            end_date: Fecha de fin del rango

        Returns:
            List[Competition]: Competiciones activas en el rango
        """
        # Estados considerados "activos" (no DRAFT, CANCELLED, COMPLETED)
        active_statuses = [
            CompetitionStatus.ACTIVE.value,
            CompetitionStatus.CLOSED.value,
            CompetitionStatus.IN_PROGRESS.value,
        ]

        statement = (
            select(Competition)
            .where(
                and_(
                    Competition._status_value.in_(active_statuses),
                    Competition._start_date <= end_date,
                    Competition._end_date >= start_date,
                )
            )
            .order_by(Competition._start_date.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def exists_with_name(self, name: CompetitionName, creator_id: UserId) -> bool:
        """
        Verifica si existe una competición con el nombre especificado para un creador.

        Previene duplicados del mismo creador con el mismo nombre.

        Args:
            name: Nombre de la competición (Value Object)
            creator_id: ID del usuario creador

        Returns:
            bool: True si existe, False si no existe

        Note:
            Usamos _name_value (atributo privado) porque name es un composite.
        """
        statement = (
            select(func.count())
            .select_from(Competition)
            .where(
                and_(
                    Competition._name_value == str(name),
                    Competition.creator_id == creator_id,
                )
            )
        )
        result = await self._session.execute(statement)
        return result.scalar_one() > 0

    async def find_all(self, limit: int = 100, offset: int = 0) -> list[Competition]:
        """
        Obtiene todas las competiciones con paginación.

        Args:
            limit: Número máximo de resultados (paginación)
            offset: Número de resultados a saltar (paginación)

        Returns:
            List[Competition]: Lista de todas las competiciones
        """
        statement = (
            select(Competition)
            .order_by(Competition.created_at.desc())  # Más recientes primero
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def count_by_creator(self, creator_id: UserId) -> int:
        """
        Cuenta el total de competiciones creadas por un usuario.

        Args:
            creator_id: ID del usuario creador

        Returns:
            int: Número total de competiciones
        """
        statement = (
            select(func.count())
            .select_from(Competition)
            .where(Competition.creator_id == creator_id)
        )
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def find_by_filters(
        self,
        search_name: str | None = None,
        search_creator: str | None = None,
        status: CompetitionStatus | None = None,
        creator_id: UserId | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Competition]:
        """
        Busca competiciones aplicando múltiples filtros opcionales.

        Implementa búsqueda case-insensitive con ILIKE:
        - search_name: Busca en competition.name
        - search_creator: Busca en creator.first_name OR creator.last_name

        Args:
            search_name: Texto a buscar en nombre de competición
            search_creator: Texto a buscar en nombre del creador
            status: Filtrar por estado
            creator_id: Filtrar por creador específico
            limit: Máximo de resultados
            offset: Saltar N resultados

        Returns:
            List[Competition]: Competiciones que cumplen los criterios
        """
        # Import here to avoid circular dependency with User module
        from src.modules.user.domain.entities.user import User  # noqa: PLC0415

        # Construir query base
        query = select(Competition)

        # Si hay búsqueda por creador, necesitamos hacer JOIN con User
        if search_creator:
            query = query.join(User, Competition.creator_id == User.id)

        # Lista de condiciones WHERE
        conditions = []

        # Filtro: search_name (búsqueda parcial case-insensitive)
        if search_name:
            conditions.append(Competition._name_value.ilike(f"%{search_name}%"))

        # Filtro: search_creator (búsqueda en first_name OR last_name)
        if search_creator:
            conditions.append(
                or_(
                    User.first_name.ilike(f"%{search_creator}%"),
                    User.last_name.ilike(f"%{search_creator}%"),
                )
            )

        # Apply filter: competition status
        if status:
            conditions.append(Competition._status_value == status.value)

        # Apply filter: creator user ID
        if creator_id:
            conditions.append(Competition.creator_id == creator_id)

        # Aplicar condiciones si existen
        if conditions:
            query = query.where(and_(*conditions))

        # Ordenar y paginar
        query = query.order_by(Competition.created_at.desc()).limit(limit).offset(offset)

        # Ejecutar query
        result = await self._session.execute(query)
        return list(result.scalars().all())
