"""
Enrollment Repository - SQLAlchemy Implementation.

Implementación concreta del repositorio de inscripciones usando SQLAlchemy async.
"""

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.repositories.enrollment_repository_interface import (
    EnrollmentRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import (
    EnrollmentStatus,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyEnrollmentRepository(EnrollmentRepositoryInterface):
    """
    Implementación asíncrona del repositorio de inscripciones con SQLAlchemy.

    Maneja la persistencia de la entidad Enrollment usando async/await.
    """

    def __init__(self, session: AsyncSession):
        """
        Constructor del repositorio.

        Args:
            session: Sesión asíncrona de SQLAlchemy
        """
        self._session = session

    async def add(self, enrollment: Enrollment) -> None:
        """
        Agrega una nueva inscripción al repositorio.

        Args:
            enrollment: Entidad Enrollment a guardar
        """
        self._session.add(enrollment)

    async def update(self, enrollment: Enrollment) -> None:
        """
        Actualiza una inscripción existente.

        Args:
            enrollment: Entidad Enrollment con datos actualizados
        """
        self._session.add(enrollment)

    async def find_by_id(self, enrollment_id: EnrollmentId) -> Enrollment | None:
        """
        Busca una inscripción por su ID único.

        Args:
            enrollment_id: ID de la inscripción

        Returns:
            Optional[Enrollment]: La inscripción encontrada o None
        """
        return await self._session.get(Enrollment, enrollment_id)

    async def find_by_competition(
        self, competition_id: CompetitionId, limit: int = 100, offset: int = 0
    ) -> list[Enrollment]:
        """
        Busca todas las inscripciones de una competición.

        Args:
            competition_id: ID de la competición
            limit: Número máximo de resultados
            offset: Número de resultados a saltar

        Returns:
            List[Enrollment]: Lista de inscripciones de la competición
        """
        statement = (
            select(Enrollment)
            .where(Enrollment._competition_id == competition_id)
            .order_by(Enrollment._created_at.asc())  # Primero en inscribirse, primero en lista
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_by_competition_and_status(
        self,
        competition_id: CompetitionId,
        status: EnrollmentStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Enrollment]:
        """
        Busca inscripciones de una competición filtradas por estado.

        Args:
            competition_id: ID de la competición
            status: Estado de inscripción (enum)
            limit: Número máximo de resultados
            offset: Número de resultados a saltar

        Returns:
            List[Enrollment]: Lista de inscripciones con el estado especificado

        Note:
            Usamos el atributo privado _status_value porque status es un composite.
        """
        statement = (
            select(Enrollment)
            .where(
                and_(
                    Enrollment._competition_id == competition_id,
                    Enrollment._status_value == status.value,
                )
            )
            .order_by(Enrollment._created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_by_user(
        self, user_id: UserId, limit: int = 100, offset: int = 0
    ) -> list[Enrollment]:
        """
        Busca todas las inscripciones de un usuario.

        Args:
            user_id: ID del usuario
            limit: Número máximo de resultados
            offset: Número de resultados a saltar

        Returns:
            List[Enrollment]: Lista de inscripciones del usuario
        """
        statement = (
            select(Enrollment)
            .where(Enrollment._user_id == user_id)
            .order_by(Enrollment._created_at.desc())  # Más recientes primero
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_by_user_and_competition(
        self, user_id: UserId, competition_id: CompetitionId
    ) -> Enrollment | None:
        """
        Busca un enrollment específico de un usuario en una competición.

        Args:
            user_id: ID del usuario
            competition_id: ID de la competición

        Returns:
            Enrollment | None: El enrollment si existe, None si no existe
        """
        statement = select(Enrollment).where(
            and_(
                Enrollment._user_id == user_id,
                Enrollment._competition_id == competition_id,
            )
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def exists_for_user_in_competition(
        self, user_id: UserId, competition_id: CompetitionId
    ) -> bool:
        """
        Verifica si existe una inscripción para un usuario en una competición.

        Útil para prevenir inscripciones duplicadas (constraint de BD también lo hace).

        Args:
            user_id: ID del usuario
            competition_id: ID de la competición

        Returns:
            bool: True si existe, False si no existe
        """
        statement = (
            select(func.count())
            .select_from(Enrollment)
            .where(
                and_(
                    Enrollment._user_id == user_id,
                    Enrollment._competition_id == competition_id,
                )
            )
        )
        result = await self._session.execute(statement)
        return result.scalar_one() > 0

    async def count_approved(self, competition_id: CompetitionId) -> int:
        """
        Cuenta el total de inscripciones aprobadas en una competición.

        Args:
            competition_id: ID de la competición

        Returns:
            int: Número total de inscripciones aprobadas
        """
        statement = (
            select(func.count())
            .select_from(Enrollment)
            .where(
                and_(
                    Enrollment._competition_id == competition_id,
                    Enrollment._status_value == EnrollmentStatus.APPROVED.value,
                )
            )
        )
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def count_approved_by_competition(self, competition_id: CompetitionId) -> int:
        """
        Alias para count_approved.
        Cuenta el total de inscripciones aprobadas en una competición.

        Args:
            competition_id: ID de la competición

        Returns:
            int: Número total de inscripciones aprobadas
        """
        return await self.count_approved(competition_id)

    async def count_active_by_user(self, user_id: UserId) -> int:
        """
        Cuenta el total de inscripciones activas de un usuario.

        Considera activas las inscripciones con estado APPROVED o REQUESTED.

        Args:
            user_id: ID del usuario

        Returns:
            int: Número total de inscripciones activas
        """
        statement = (
            select(func.count())
            .select_from(Enrollment)
            .where(
                and_(
                    Enrollment._user_id == user_id,
                    Enrollment._status_value.in_(
                        [
                            EnrollmentStatus.APPROVED.value,
                            EnrollmentStatus.REQUESTED.value,
                        ]
                    ),
                )
            )
        )
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def count_pending(self, competition_id: CompetitionId) -> int:
        """
        Cuenta el total de inscripciones pendientes (REQUESTED) en una competición.

        Args:
            competition_id: ID de la competición

        Returns:
            int: Número total de inscripciones con estado REQUESTED
        """
        statement = (
            select(func.count())
            .select_from(Enrollment)
            .where(
                and_(
                    Enrollment._competition_id == competition_id,
                    Enrollment._status_value == EnrollmentStatus.REQUESTED.value,
                )
            )
        )
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def find_by_competition_and_team(
        self, competition_id: CompetitionId, team_id: str
    ) -> list[Enrollment]:
        """
        Busca todas las inscripciones asignadas a un equipo específico.

        Args:
            competition_id: ID de la competición
            team_id: ID del equipo (típicamente "1" o "2")

        Returns:
            List[Enrollment]: Lista de inscripciones del equipo
        """
        statement = (
            select(Enrollment)
            .where(
                and_(
                    Enrollment._competition_id == competition_id,
                    Enrollment._team_id == team_id,
                )
            )
            .order_by(Enrollment._created_at.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())
