"""
IGolfCourseRepository - Interfaz del repositorio de campos de golf.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.modules.user.domain.value_objects.user_id import UserId

from ..entities.golf_course import GolfCourse
from ..value_objects.approval_status import ApprovalStatus
from ..value_objects.golf_course_id import GolfCourseId


@dataclass(frozen=True)
class ApprovedCourseSearch:
    """
    Criterios para buscar entre los campos aprobados.

    Van juntos en un objeto y no como siete parámetros sueltos porque casi
    todos son opcionales y el orden se vuelve imposible de recordar.
    """

    country_code: str | None = None
    name: str | None = None
    limit: int | None = None
    offset: int = 0
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float | None = None

    @property
    def has_position(self) -> bool:
        """True si hay una posición desde la que medir distancias."""
        return self.latitude is not None and self.longitude is not None


@dataclass(frozen=True)
class ApprovedCoursePage:
    """
    Una página de campos aprobados.

    `total` cuenta los que cumplen el filtro, no los devueltos: es lo que
    necesita el cliente para saber si merece la pena pedir la página siguiente.
    """

    courses: list[GolfCourse]
    total: int
    distances_km: dict[str, float] = field(default_factory=dict)


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
    async def search_approved(self, search: ApprovedCourseSearch) -> ApprovedCoursePage:
        """
        Busca entre los campos aprobados aplicando los filtros que se le pasen.

        Sin criterios devuelve todos los aprobados, que es lo que hacía el
        listado antes de tener búsqueda.

        Args:
            search: Criterios de búsqueda

        Returns:
            La página pedida, el total que cumple el filtro y las distancias
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
    async def count_by_approval_status(self, approval_status: ApprovalStatus) -> int:
        """
        Cuenta campos de golf por estado de aprobación, sin materializarlos.

        Args:
            approval_status: Estado a contar (PENDING_APPROVAL, APPROVED, REJECTED)

        Returns:
            Número de campos con ese estado
        """
        pass

    @abstractmethod
    async def count_by_creator(self, creator_id: UserId) -> int:
        """
        Cuenta campos creados por un usuario específico, sin materializarlos.

        Args:
            creator_id: ID del creator

        Returns:
            Número de campos creados por ese usuario
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
