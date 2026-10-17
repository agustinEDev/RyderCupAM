"""
Saved Hole Repository Interface - Golf Course Module Domain Layer.

La línea de referencia que el admin guarda de cada hoyo (BE #575, 17 oct 2026):
una por campo y hoyo.
"""

from abc import ABC, abstractmethod

from ..entities.saved_hole import SavedHole
from ..value_objects.golf_course_id import GolfCourseId


class ISavedHoleRepository(ABC):
    """Repositorio de las líneas guardadas de los hoyos."""

    @abstractmethod
    async def save(self, hole: SavedHole) -> None:
        """Guarda la línea del hoyo; si ya había una, la sustituye."""

    @abstractmethod
    async def get(self, golf_course_id: GolfCourseId, hole_number: int) -> SavedHole | None:
        """La línea guardada de ese hoyo, o None."""

    @abstractmethod
    async def list_by_course(self, golf_course_id: GolfCourseId) -> list[SavedHole]:
        """Las líneas guardadas del campo, por número de hoyo."""

    @abstractmethod
    async def delete(self, golf_course_id: GolfCourseId, hole_number: int) -> bool:
        """Quita la línea del hoyo (se reabre); False si no había."""
