"""In-Memory Golf Course Repository para testing."""

import math

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.repositories.golf_course_repository import (
    ApprovedCoursePage,
    ApprovedCourseSearch,
    IGolfCourseRepository,
)
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

EARTH_RADIUS_KM = 6371.0


def _haversine_km(
    from_latitude: float, from_longitude: float, to_latitude: float, to_longitude: float
) -> float:
    """
    Distancia en kilómetros entre dos puntos, la misma fórmula que el SQL real.

    Tiene que dar lo mismo que `_distance_km` del repositorio de verdad: si el
    doble midiera distinto, los tests darían por bueno un orden que en
    producción sale en otro sitio.
    """
    from_latitude_rad = math.radians(from_latitude)
    to_latitude_rad = math.radians(to_latitude)
    half_latitude_delta = (to_latitude_rad - from_latitude_rad) / 2
    half_longitude_delta = (math.radians(to_longitude) - math.radians(from_longitude)) / 2

    chord = (
        math.sin(half_latitude_delta) ** 2
        + math.cos(from_latitude_rad)
        * math.cos(to_latitude_rad)
        * math.sin(half_longitude_delta) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(chord)))


class InMemoryGolfCourseRepository(IGolfCourseRepository):
    """
    Implementación en memoria del repositorio de campos de golf para testing.

    Mantiene los campos en un diccionario en memoria.
    """

    def __init__(self):
        self._golf_courses: dict[str, GolfCourse] = {}

    async def save(self, golf_course: GolfCourse) -> None:
        """
        Persiste un campo de golf en memoria.

        Args:
            golf_course: Campo a persistir
        """
        self._golf_courses[str(golf_course.id.value)] = golf_course

    async def add(self, golf_course: GolfCourse) -> None:
        """
        Alias de save para consistencia con otros repositorios.

        Args:
            golf_course: Campo a añadir
        """
        await self.save(golf_course)

    async def find_by_id(self, golf_course_id: GolfCourseId) -> GolfCourse | None:
        """
        Busca un campo por ID.

        Args:
            golf_course_id: ID del campo

        Returns:
            GolfCourse si existe, None si no
        """
        return self._golf_courses.get(str(golf_course_id.value))

    async def find_by_approval_status(self, approval_status: ApprovalStatus) -> list[GolfCourse]:
        """
        Busca campos por estado de aprobación.

        Args:
            approval_status: Estado a filtrar

        Returns:
            Lista de campos con ese estado
        """
        return [gc for gc in self._golf_courses.values() if gc.approval_status == approval_status]

    async def search_approved(self, search: ApprovedCourseSearch) -> ApprovedCoursePage:
        """
        Busca entre los campos aprobados aplicando los filtros que se le pasen.

        Reproduce lo que hace el repositorio real, incluido excluir los campos
        sin coordenadas cuando se busca por cercanía: si el doble fuera más
        permisivo, los tests darían por buena una búsqueda que en producción
        devuelve otra cosa.

        Args:
            search: Criterios de búsqueda

        Returns:
            La página pedida, el total que cumple el filtro y las distancias
        """
        courses = await self.find_by_approval_status(ApprovalStatus.APPROVED)

        if search.country_code:
            # Se normaliza con el value object, como hace el repositorio real:
            # si aquí bastara con 'es' en minúsculas y allí no, el test pasaría
            # y la búsqueda de verdad devolvería vacío
            wanted = CountryCode(search.country_code)
            courses = [gc for gc in courses if gc.country_code == wanted]

        if search.name:
            needle = search.name.casefold()
            courses = [gc for gc in courses if needle in gc.name.casefold()]

        distances: dict[str, float] = {}
        if search.has_position:
            located = []
            for course in courses:
                location = course.location
                if location.latitude is None or location.longitude is None:
                    continue
                distance = _haversine_km(
                    search.latitude, search.longitude, location.latitude, location.longitude
                )
                if search.radius_km is not None and distance > search.radius_km:
                    continue
                distances[str(course.id)] = round(distance, 3)
                located.append(course)
            # El id desempata, igual que en el repositorio real: sin un orden
            # total, dos campos empatados pueden intercambiarse entre páginas y
            # el usuario ve uno repetido y se pierde otro
            courses = sorted(located, key=lambda gc: (distances[str(gc.id)], str(gc.id)))
        else:
            courses = sorted(courses, key=lambda gc: (-gc.created_at.timestamp(), str(gc.id)))

        total = len(courses)
        page = courses[search.offset :]
        if search.limit is not None:
            page = page[: search.limit]

        return ApprovedCoursePage(
            courses=page,
            total=total,
            distances_km={
                str(gc.id): distances[str(gc.id)] for gc in page if str(gc.id) in distances
            },
        )

    async def find_pending_approval(self) -> list[GolfCourse]:
        """
        Busca todos los campos pendientes de aprobación.

        Returns:
            Lista de campos PENDING_APPROVAL
        """
        return await self.find_by_approval_status(ApprovalStatus.PENDING_APPROVAL)

    async def find_by_creator(self, creator_id: UserId) -> list[GolfCourse]:
        """
        Busca campos creados por un usuario específico.

        Args:
            creator_id: ID del creator

        Returns:
            Lista de campos creados por ese usuario
        """
        return [gc for gc in self._golf_courses.values() if gc.requested_by == creator_id]

    async def count_by_approval_status(self, approval_status: ApprovalStatus) -> int:
        """
        Cuenta campos por estado de aprobación.

        Args:
            approval_status: Estado a contar

        Returns:
            Número de campos con ese estado
        """
        return len(await self.find_by_approval_status(approval_status))

    async def count_by_creator(self, creator_id: UserId) -> int:
        """
        Cuenta campos creados por un usuario específico.

        Args:
            creator_id: ID del creator

        Returns:
            Número de campos creados por ese usuario
        """
        return len(await self.find_by_creator(creator_id))

    async def delete(self, golf_course_id: GolfCourseId) -> None:
        """
        Elimina un campo de golf (hard delete).

        Args:
            golf_course_id: ID del campo a eliminar
        """
        self._golf_courses.pop(str(golf_course_id.value), None)

    def clear(self) -> None:
        """
        Limpia todos los campos (útil para tests).
        """
        self._golf_courses.clear()
