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
        """
        Guarda el mapa.

        Para actualizar, se guarda el mismo mapa que se leyó con
        `find_by_golf_course_id`. Guardar un mapa recién creado para un campo
        que ya tiene uno es un error: se lee y se reimporta.
        """

    @abstractmethod
    async def find_by_golf_course_id(self, golf_course_id: GolfCourseId) -> CourseHoleMap | None:
        """El mapa del campo, o None si no tiene."""

    @abstractmethod
    async def find_by_golf_course_id_for_update(
        self, golf_course_id: GolfCourseId
    ) -> CourseHoleMap | None:
        """
        El mapa del campo leído de la base de datos (no la copia que ya tuviera
        la sesión) y bloqueado hasta el final de la transacción: para escribir
        sobre lo último que hay, sin que nadie lo cambie entretanto. Bloquea
        también cuando el campo aún no tiene mapa, para que dos importaciones a
        la vez no lo creen las dos.
        """

    @abstractmethod
    async def find_pending(self) -> list[CourseHoleMap]:
        """Los mapas pendientes de revisión, del más antiguo al más reciente."""
