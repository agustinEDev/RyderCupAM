"""
GolfCourseRepository - Implementación SQLAlchemy del repositorio de campos de golf.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper import (
    golf_courses_table,
)
from src.modules.user.domain.value_objects.user_id import UserId


class GolfCourseRepository(IGolfCourseRepository):
    """
    Implementación SQLAlchemy del repositorio de campos de golf.

    Responsabilidades:
    - Persistir/actualizar GolfCourse aggregates
    - Hidratar entidades desde BD
    - Queries complejas (find_by_approval_status, find_by_creator, etc.)
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, golf_course: GolfCourse) -> None:
        """
        Persiste un campo de golf (create o update).

        Args:
            golf_course: Campo a persistir
        """
        # SQLAlchemy detecta automáticamente si es INSERT o UPDATE
        # gracias al imperative mapping y el session tracking
        self._session.add(golf_course)
        await self._session.flush()

    async def find_by_id(self, golf_course_id: GolfCourseId) -> GolfCourse | None:
        """
        Busca un campo de golf por ID.

        Args:
            golf_course_id: ID del campo

        Returns:
            GolfCourse si existe, None si no
        """
        stmt = (
            select(GolfCourse)
            .where(golf_courses_table.c.id == golf_course_id.value)
            .options(
                joinedload(GolfCourse._tees),
                joinedload(GolfCourse._holes),
            )
        )
        result = await self._session.execute(stmt)
        result = result.unique()
        return result.scalar_one_or_none()

    async def find_by_approval_status(self, approval_status: ApprovalStatus) -> list[GolfCourse]:
        """
        Busca campos de golf por estado de aprobación.

        Args:
            approval_status: Estado a filtrar (PENDING_APPROVAL, APPROVED, REJECTED)

        Returns:
            Lista de campos con ese estado
        """
        stmt = (
            select(GolfCourse)
            .where(golf_courses_table.c.approval_status == approval_status)
            .options(
                joinedload(GolfCourse._tees),
                joinedload(GolfCourse._holes),
            )
            .order_by(golf_courses_table.c.created_at.desc())
        )
        result = await self._session.execute(stmt)
        result = result.unique()
        return list(result.scalars().all())

    async def find_approved(self) -> list[GolfCourse]:
        """
        Busca todos los campos aprobados.

        Returns:
            Lista de campos con status APPROVED
        """
        return await self.find_by_approval_status(ApprovalStatus.APPROVED)

    async def find_pending_approval(self) -> list[GolfCourse]:
        """
        Busca todos los campos pendientes de aprobación.

        Returns:
            Lista de campos con status PENDING_APPROVAL
        """
        return await self.find_by_approval_status(ApprovalStatus.PENDING_APPROVAL)

    async def find_by_creator(self, creator_id: UserId) -> list[GolfCourse]:
        """
        Busca campos creados por un usuario específico.

        Args:
            creator_id: ID del creator

        Returns:
            Lista de campos creados por ese usuario
        """
        stmt = (
            select(GolfCourse)
            .where(golf_courses_table.c.creator_id == creator_id.value)
            .options(
                joinedload(GolfCourse._tees),
                joinedload(GolfCourse._holes),
            )
            .order_by(golf_courses_table.c.created_at.desc())
        )
        result = await self._session.execute(stmt)
        result = result.unique()
        return list(result.scalars().all())

    async def delete(self, golf_course_id: GolfCourseId) -> None:
        """
        Elimina un campo de golf (hard delete).

        Cascade delete automático con tees y holes (configurado en mapper).

        Args:
            golf_course_id: ID del campo a eliminar
        """
        golf_course = await self.find_by_id(golf_course_id)
        if golf_course:
            await self._session.delete(golf_course)
            await self._session.flush()
