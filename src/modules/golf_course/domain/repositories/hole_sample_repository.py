"""
Hole Sample Repository Interface - Golf Course Module Domain Layer.

Las muestras anónimas de hoyo (BE #532, 16 oct 2026): como mucho tres por
campo, hoyo y barra, sin quién las mandó y sin la hora.
"""

from abc import ABC, abstractmethod
from uuid import UUID

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
    async def exists(self, sample_id: UUID) -> bool:
        """Si ya hay una muestra con ese id (en cualquier campo u hoyo)."""

    @abstractmethod
    async def count_for_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> int:
        """Cuántas muestras hay guardadas del hoyo, de cualquier barra."""

    @abstractmethod
    async def add(self, sample: HoleSample) -> bool:
        """
        Guarda una muestra nueva, al final del orden de llegada. Si su id ya
        existe no hace nada y devuelve False (dos envíos a la vez del mismo id
        no chocan).
        """

    @abstractmethod
    async def list_by_course(self, golf_course_id: GolfCourseId) -> list[HoleSample]:
        """Las muestras del campo, por hoyo y, en cada hoyo, en orden de llegada."""
