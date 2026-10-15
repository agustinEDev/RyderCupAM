"""
Hole Map Repository Interface - Golf Course Module Domain Layer.

Contrato de persistencia del mapa de hoyos de un recorrido (BE #532). Un campo
tiene como mucho un mapa, así que se busca por el propio campo.
"""

from abc import ABC, abstractmethod

from ..entities.course_hole_map import CourseHoleMap
from ..value_objects.golf_course_id import GolfCourseId


class IHoleMapRepository(ABC):
    """Repositorio de mapas de hoyos."""

    @abstractmethod
    async def save(self, hole_map: CourseHoleMap) -> None:
        """Guarda el mapa; si el campo ya tenía uno leído en esta transacción, lo actualiza."""

    @abstractmethod
    async def find_by_golf_course_id(self, golf_course_id: GolfCourseId) -> CourseHoleMap | None:
        """El mapa del campo, o None si no tiene."""

    @abstractmethod
    async def find_pending(self) -> list[CourseHoleMap]:
        """Los mapas pendientes de revisión, del más antiguo al más reciente."""
