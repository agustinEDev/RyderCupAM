"""
Hole Sample Repository Interface - Golf Course Module Domain Layer.

Las muestras anónimas de hoyo (BE #532, 16 oct 2026): como mucho tres por
campo y hoyo, sin quién las mandó.
"""

from abc import ABC, abstractmethod

from ..entities.hole_sample import HoleSample
from ..value_objects.golf_course_id import GolfCourseId


class IHoleSampleRepository(ABC):
    """Repositorio de muestras de hoyo."""

    @abstractmethod
    async def lock_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> None:
        """
        Bloquea el hoyo hasta el final de la transacción, para contar y guardar
        sin que otra muestra del mismo hoyo se cuele entre medias (y queden más
        de tres). Las de otros hoyos no esperan.
        """

    @abstractmethod
    async def count_for_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> int:
        """Cuántas muestras hay guardadas de ese hoyo."""

    @abstractmethod
    async def add(self, sample: HoleSample) -> None:
        """Guarda una muestra nueva."""

    @abstractmethod
    async def list_by_course(self, golf_course_id: GolfCourseId) -> list[HoleSample]:
        """Las muestras del campo, por hoyo y, en cada hoyo, de la más antigua a la más nueva."""
