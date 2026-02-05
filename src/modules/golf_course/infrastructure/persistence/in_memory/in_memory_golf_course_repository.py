"""In-Memory Golf Course Repository para testing."""

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.repositories.golf_course_repository import (
    IGolfCourseRepository,
)
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryGolfCourseRepository(IGolfCourseRepository):
    """
    Implementación en memoria del repositorio de campos de golf para testing.

    Mantiene los campos en un diccionario en memoria.
    """

    def __init__(self):
        self._golf_courses: dict[str, GolfCourse] = {}

    async def save(self, golf_course: GolfCourse) -> None:
        """
        Persiste un campo de golf en memoria.

        Args:
            golf_course: Campo a persistir
        """
        self._golf_courses[str(golf_course.id.value)] = golf_course

    async def add(self, golf_course: GolfCourse) -> None:
        """
        Alias de save para consistencia con otros repositorios.

        Args:
            golf_course: Campo a añadir
        """
        await self.save(golf_course)

    async def find_by_id(self, golf_course_id: GolfCourseId) -> GolfCourse | None:
        """
        Busca un campo por ID.

        Args:
            golf_course_id: ID del campo

        Returns:
            GolfCourse si existe, None si no
        """
        return self._golf_courses.get(str(golf_course_id.value))

    async def find_by_approval_status(self, approval_status: ApprovalStatus) -> list[GolfCourse]:
        """
        Busca campos por estado de aprobación.

        Args:
            approval_status: Estado a filtrar

        Returns:
            Lista de campos con ese estado
        """
        return [gc for gc in self._golf_courses.values() if gc.approval_status == approval_status]

    async def find_approved(self, country_code: str | None = None) -> list[GolfCourse]:
        """
        Busca todos los campos aprobados, opcionalmente filtrados por país.

        Args:
            country_code: Código ISO del país para filtrar (opcional)

        Returns:
            Lista de campos APPROVED
        """
        approved = await self.find_by_approval_status(ApprovalStatus.APPROVED)
        if country_code:
            return [gc for gc in approved if gc.country_code.value == country_code]
        return approved

    async def find_pending_approval(self) -> list[GolfCourse]:
        """
        Busca todos los campos pendientes de aprobación.

        Returns:
            Lista de campos PENDING_APPROVAL
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
        return [gc for gc in self._golf_courses.values() if gc.requested_by == creator_id]

    async def delete(self, golf_course_id: GolfCourseId) -> None:
        """
        Elimina un campo de golf (hard delete).

        Args:
            golf_course_id: ID del campo a eliminar
        """
        self._golf_courses.pop(str(golf_course_id.value), None)

    def clear(self) -> None:
        """
        Limpia todos los campos (útil para tests).
        """
        self._golf_courses.clear()
