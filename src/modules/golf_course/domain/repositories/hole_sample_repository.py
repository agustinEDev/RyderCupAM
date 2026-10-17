"""
Hole Sample Repository Interface - Golf Course Module Domain Layer.

Las muestras anónimas de hoyo (BE #532): como mucho tres por campo y hoyo, de
cualquier barra (BE #575, 17 oct), y de ellas como mucho una solo green; sin
quién las mandó y sin la hora.
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
    async def has_green_only(self, golf_course_id: GolfCourseId, hole_number: int) -> bool:
        """Si el hoyo ya tiene una muestra solo green (sin salida)."""

    @abstractmethod
    async def add(self, sample: HoleSample) -> bool:
        """
        Guarda una muestra nueva, al final del orden de llegada. Si su id ya
        existe no hace nada y devuelve False (dos envíos a la vez del mismo id
        no chocan).
        """

    @abstractmethod
    async def delete(self, golf_course_id: GolfCourseId, sample_id: UUID) -> bool:
        """Borra esa muestra del campo; False si no está en él (BE #575: el admin)."""

    @abstractmethod
    async def count_by_hole(self) -> list[tuple[GolfCourseId, int, int]]:
        """De todos los campos, cuántas muestras hay por hoyo: (campo, hoyo, cuántas). Para el admin."""

    @abstractmethod
    async def list_by_course(self, golf_course_id: GolfCourseId) -> list[HoleSample]:
        """Las muestras del campo, por hoyo y, en cada hoyo, en orden de llegada."""
