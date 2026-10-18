"""
Hole Report Repository Interface - Golf Course Module Domain Layer.

Los reportes de hoyo (entrega 7, 18 oct 2026): como mucho tres abiertos por
campo y hoyo; sin quién los mandó y sin la hora. Guardar la línea del hoyo los
cierra todos y el admin puede descartar uno: cerrar es borrar.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from ..entities.hole_report import HoleReport
from ..value_objects.golf_course_id import GolfCourseId


class IHoleReportRepository(ABC):
    """Repositorio de reportes de hoyo."""

    @abstractmethod
    async def lock_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> None:
        """
        Bloquea el hoyo hasta el final de la transacción, para contar y guardar
        sin que otro reporte del mismo hoyo se cuele entre medias (y queden más
        de tres). Los de otros hoyos no esperan.
        """

    @abstractmethod
    async def exists(self, report_id: UUID) -> bool:
        """Si ya hay un reporte con ese id (en cualquier campo u hoyo)."""

    @abstractmethod
    async def count_for_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> int:
        """Cuántos reportes abiertos tiene el hoyo."""

    @abstractmethod
    async def add(self, report: HoleReport) -> bool:
        """
        Guarda un reporte nuevo, al final del orden de llegada. Si su id ya
        existe no hace nada y devuelve False.
        """

    @abstractmethod
    async def delete(self, golf_course_id: GolfCourseId, report_id: UUID) -> bool:
        """Borra (descarta) ese reporte del campo; False si no está en él."""

    @abstractmethod
    async def delete_for_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> int:
        """Borra los reportes del hoyo (se guardó su línea); devuelve cuántos."""

    @abstractmethod
    async def count_by_hole(self) -> list[tuple[GolfCourseId, int, int]]:
        """De todos los campos, cuántos reportes hay por hoyo: (campo, hoyo, cuántos)."""

    @abstractmethod
    async def list_by_course(self, golf_course_id: GolfCourseId) -> list[HoleReport]:
        """Los reportes del campo, por hoyo y, en cada hoyo, en orden de llegada."""
