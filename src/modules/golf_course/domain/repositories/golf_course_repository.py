"""
IGolfCourseRepository - Interfaz del repositorio de campos de golf.
"""

from abc import ABC, abstractmethod

from src.modules.user.domain.value_objects.user_id import UserId

from ..entities.golf_course import GolfCourse
from ..value_objects.approval_status import ApprovalStatus
from ..value_objects.golf_course_id import GolfCourseId


class IGolfCourseRepository(ABC):
    """
    Interfaz del repositorio de campos de golf.

    Define el contrato para persistencia de GolfCourse.
    """

    @abstractmethod
    async def save(self, golf_course: GolfCourse) -> None:
        """
        Persiste un campo de golf (create o update).

        Args:
            golf_course: Campo a persistir
        """
        pass

    @abstractmethod
    async def find_by_id(self, golf_course_id: GolfCourseId) -> GolfCourse | None:
        """
        Busca un campo de golf por ID.

        Args:
            golf_course_id: ID del campo

        Returns:
            GolfCourse si existe, None si no
        """
        pass

    @abstractmethod
    async def find_by_approval_status(self, approval_status: ApprovalStatus) -> list[GolfCourse]:
        """
        Busca campos de golf por estado de aprobación.

        Args:
            approval_status: Estado a filtrar (PENDING_APPROVAL, APPROVED, REJECTED)

        Returns:
            Lista de campos con ese estado
        """
        pass

    @abstractmethod
    async def find_approved(self) -> list[GolfCourse]:
        """
        Busca todos los campos aprobados.

        Returns:
            Lista de campos con status APPROVED
        """
        pass

    @abstractmethod
    async def find_pending_approval(self) -> list[GolfCourse]:
        """
        Busca todos los campos pendientes de aprobación.

        Returns:
            Lista de campos con status PENDING_APPROVAL
        """
        pass

    @abstractmethod
    async def find_by_creator(self, creator_id: UserId) -> list[GolfCourse]:
        """
        Busca campos creados por un usuario específico.

        Args:
            creator_id: ID del creator

        Returns:
            Lista de campos creados por ese usuario
        """
        pass

    @abstractmethod
    async def delete(self, golf_course_id: GolfCourseId) -> None:
        """
        Elimina un campo de golf (hard delete).

        Usado para limpiar campos rechazados (cascade delete con tees y holes).

        Args:
            golf_course_id: ID del campo a eliminar
        """
        pass
