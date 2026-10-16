"""
Hole Sample Repository Interface - Golf Course Module Domain Layer.

Las muestras anónimas de hoyo (BE #532, 16 oct 2026): como mucho tres por
campo, hoyo y barra, sin quién las mandó y sin la hora.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from src.shared.domain.value_objects.gender import Gender

from ..entities.hole_sample import HoleSample
from ..value_objects.golf_course_id import GolfCourseId
from ..value_objects.tee_color import TeeColor


class IHoleSampleRepository(ABC):
    """Repositorio de muestras de hoyo."""

    @abstractmethod
    async def lock_tee(
        self,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee_color: TeeColor,
        tee_gender: Gender | None,
    ) -> None:
        """
        Bloquea esa barra del hoyo hasta el final de la transacción, para contar
        y guardar sin que otra muestra de la misma barra se cuele entre medias (y
        queden más de tres). Las de otras barras u otros hoyos no esperan.
        """

    @abstractmethod
    async def exists(self, sample_id: UUID) -> bool:
        """Si ya hay una muestra con ese id (en cualquier campo u hoyo)."""

    @abstractmethod
    async def count_for_tee(
        self,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee_color: TeeColor,
        tee_gender: Gender | None,
    ) -> int:
        """Cuántas muestras hay guardadas de esa barra del hoyo (None = sin género)."""

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
