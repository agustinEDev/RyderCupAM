"""
Hole Mark Repository Interface - Golf Course Module Domain Layer.

Las marcas de hoyo de los jugadores (BE #532, PR C): una por jugador y hoyo.
"""

from abc import ABC, abstractmethod

from src.modules.user.domain.value_objects.user_id import UserId

from ..entities.hole_mark import HoleMark
from ..value_objects.golf_course_id import GolfCourseId


class IHoleMarkRepository(ABC):
    """Repositorio de marcas de hoyo."""

    @abstractmethod
    async def save(self, mark: HoleMark) -> None:
        """
        Guarda la marca. Si el jugador ya tenía una en ese hoyo, la sustituye
        (conserva cuándo marcó la primera vez), salvo que la guardada sea más
        nueva: entonces se queda la guardada.
        """

    @abstractmethod
    async def find(
        self, golf_course_id: GolfCourseId, hole_number: int, user_id: UserId
    ) -> HoleMark | None:
        """La marca del jugador en ese hoyo, o None."""

    @abstractmethod
    async def find_by_course_and_user(
        self, golf_course_id: GolfCourseId, user_id: UserId
    ) -> list[HoleMark]:
        """Las marcas del jugador en el campo, por orden de hoyo."""
