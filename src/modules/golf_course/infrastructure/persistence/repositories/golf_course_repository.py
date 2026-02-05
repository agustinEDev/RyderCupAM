"""
GolfCourseRepository - Implementación SQLAlchemy del repositorio de campos de golf.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper import (
    golf_course_holes_table,
    golf_course_tees_table,
    golf_courses_table,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode


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
        # Detectar si es UPDATE (objeto ya persistido) vs INSERT (nuevo)
        is_update = golf_course in self._session and self._session.is_modified(golf_course)

        if is_update:
            # WORKAROUND para bug de SQLAlchemy con cascade="all, delete-orphan"
            # y unique constraints: hacer DELETE explícito ANTES de los INSERTs
            # para evitar violaciones de UNIQUE(golf_course_id, hole_number/tee_category)

            # DELETE explícito de holes existentes
            await self._session.execute(
                delete(golf_course_holes_table).where(
                    golf_course_holes_table.c.golf_course_id == golf_course._id
                )
            )

            # DELETE explícito de tees existentes
            await self._session.execute(
                delete(golf_course_tees_table).where(
                    golf_course_tees_table.c.golf_course_id == golf_course._id
                )
            )

            # Flush para ejecutar los DELETEs antes de procesar el aggregate
            await self._session.flush()

        # Ahora sí, agregar/actualizar el aggregate
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
            .where(golf_courses_table.c.id == golf_course_id)
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

    async def find_approved(self, country_code: str | None = None) -> list[GolfCourse]:
        """
        Busca todos los campos aprobados, opcionalmente filtrados por país.

        Args:
            country_code: Código ISO del país para filtrar (opcional)

        Returns:
            Lista de campos con status APPROVED
        """
        stmt = (
            select(GolfCourse)
            .where(golf_courses_table.c.approval_status == ApprovalStatus.APPROVED)
            .options(
                joinedload(GolfCourse._tees),
                joinedload(GolfCourse._holes),
            )
            .order_by(golf_courses_table.c.created_at.desc())
        )

        if country_code:
            # Convert string to CountryCode VO for TypeDecorator compatibility
            country_code_vo = CountryCode(country_code)
            stmt = stmt.where(golf_courses_table.c.country_code == country_code_vo)

        result = await self._session.execute(stmt)
        result = result.unique()
        return list(result.scalars().all())

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
            .where(golf_courses_table.c.creator_id == creator_id)
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
