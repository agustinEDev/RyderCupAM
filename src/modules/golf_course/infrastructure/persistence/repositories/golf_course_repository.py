"""
GolfCourseRepository - Implementación SQLAlchemy del repositorio de campos de golf.
"""

import math

from sqlalchemy import delete, func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.repositories.golf_course_repository import (
    ApprovedCoursePage,
    ApprovedCourseSearch,
    IGolfCourseRepository,
)
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper import (
    golf_course_tees_table,
    golf_courses_table,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

EARTH_RADIUS_KM = 6371.0


def _escape_like(value: str) -> str:
    """Escapa los comodines de LIKE para que se busquen como caracteres normales."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _distance_km(columns, latitude: float, longitude: float):
    """
    Distancia en kilómetros entre una posición y cada campo, en SQL.

    Es la fórmula del semiverseno escrita a mano en vez de PostGIS: la imagen de
    Postgres del clúster no lo trae, y con esta cantidad de campos el recorrido
    completo de la tabla tarda menos que lo que costaría mantener la extensión
    instalada en los tres entornos.

    Se usa el semiverseno y no el teorema del coseno esférico, que sale más
    corto de escribir, porque el segundo pierde precisión justo en las
    distancias pequeñas: el coseno de un ángulo diminuto es casi 1 y la resta se
    come los decimales. Y las distancias pequeñas son exactamente el caso de
    uso, que es ordenar los campos que tienes al lado.

    El seno y el coseno de la latitud consultada se calculan aquí y no en la
    base de datos, porque son constantes para toda la consulta.
    """
    latitude_rad = math.radians(latitude)
    longitude_rad = math.radians(longitude)
    course_latitude_rad = func.radians(columns.latitude)

    half_latitude_delta = (course_latitude_rad - latitude_rad) / 2
    half_longitude_delta = (func.radians(columns.longitude) - longitude_rad) / 2

    # Al cuadrado multiplicando, y no con power(): así la expresión es la misma
    # en cualquier motor y no depende de qué nombre le dé cada uno a la función
    chord = func.sin(half_latitude_delta) * func.sin(half_latitude_delta) + math.cos(
        latitude_rad
    ) * func.cos(course_latitude_rad) * func.sin(half_longitude_delta) * func.sin(
        half_longitude_delta
    )

    # asin fuera de [-1, 1] es un error de dominio en PostgreSQL. Con el
    # semiverseno solo se rozaría en las antípodas, pero acotar es gratis
    return 2 * EARTH_RADIUS_KM * func.asin(func.least(1.0, func.sqrt(chord)))


class GolfCourseRepository(IGolfCourseRepository):
    """
    Implementación SQLAlchemy del repositorio de campos de golf.

    Responsabilidades:
    - Persistir/actualizar GolfCourse aggregates
    - Hidratar entidades desde BD
    - Queries complejas (find_by_approval_status, find_by_creator, etc.)
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, golf_course: GolfCourse) -> None:
        """
        Persiste un campo de golf (create o update).

        Args:
            golf_course: Campo a persistir
        """
        # Detectar si es UPDATE (objeto ya persistido) vs INSERT (nuevo)
        is_update = golf_course in self._session and self._session.is_modified(golf_course)

        if is_update:
            # WORKAROUND para bug de SQLAlchemy con cascade="all, delete-orphan"
            # y unique constraints: hacer DELETE explícito ANTES de los INSERTs
            # para evitar violaciones de UNIQUE(golf_course_id, color, tee_gender)
            # IMPORTANTE: Solo borrar colecciones si realmente cambiaron.
            # Raw SQL DELETE desincroniza la session identity map, causando que
            # los hijos se pierdan en updates de solo atributos escalares (ej: approve).
            # Los hoyos cuelgan de las salidas, así que basta con borrar estas:
            # sus hoyos caen por ON DELETE CASCADE. La tarjeta del campo no se
            # persiste, es derivada, y por eso no se inspecciona aquí.
            insp = inspect(golf_course)
            tees_changed = insp is not None and insp.attrs._tees.history.has_changes()

            if tees_changed:
                await self._session.execute(
                    delete(golf_course_tees_table).where(
                        golf_course_tees_table.c.golf_course_id == golf_course._id
                    )
                )
                await self._session.flush()

        # Ahora sí, agregar/actualizar el aggregate
        self._session.add(golf_course)
        await self._session.flush()

    async def find_by_id(self, golf_course_id: GolfCourseId) -> GolfCourse | None:
        """
        Busca un campo de golf por ID.

        Args:
            golf_course_id: ID del campo

        Returns:
            GolfCourse si existe, None si no
        """
        stmt = (
            select(GolfCourse)
            .where(golf_courses_table.c.id == golf_course_id)
            .options(
                joinedload(GolfCourse._tees),
            )
        )
        result = await self._session.execute(stmt)
        result = result.unique()
        return result.scalar_one_or_none()

    async def find_by_approval_status(self, approval_status: ApprovalStatus) -> list[GolfCourse]:
        """
        Busca campos de golf por estado de aprobación.

        Args:
            approval_status: Estado a filtrar (PENDING_APPROVAL, APPROVED, REJECTED)

        Returns:
            Lista de campos con ese estado
        """
        stmt = (
            select(GolfCourse)
            .where(golf_courses_table.c.approval_status == approval_status)
            .options(
                joinedload(GolfCourse._tees),
            )
            .order_by(golf_courses_table.c.created_at.desc())
        )
        result = await self._session.execute(stmt)
        result = result.unique()
        return list(result.scalars().all())

    async def search_approved(self, search: ApprovedCourseSearch) -> ApprovedCoursePage:
        """
        Busca entre los campos aprobados aplicando los filtros que se le pasen.

        Args:
            search: Criterios de búsqueda

        Returns:
            La página pedida, el total que cumple el filtro y las distancias
        """
        columns = golf_courses_table.c
        filters = [columns.approval_status == ApprovalStatus.APPROVED]

        if search.country_code:
            # Convert string to CountryCode VO for TypeDecorator compatibility
            filters.append(columns.country_code == CountryCode(search.country_code))

        if search.name:
            # El escapado importa: un nombre con '%' o '_' buscaría cualquier
            # cosa en lugar de esos caracteres. Los campos federados llevan
            # '&' y '.', pero nada impide que alguien busque por un guion bajo
            filters.append(columns.name.ilike(f"%{_escape_like(search.name)}%", escape="\\"))

        distance = None
        if search.has_position:
            distance = _distance_km(columns, search.latitude, search.longitude)
            # Sin coordenadas no hay distancia que calcular, y ordenar por NULL
            # los pondría todos al final igualmente: mejor no devolverlos
            filters.append(columns.latitude.is_not(None))
            filters.append(columns.longitude.is_not(None))
            if search.radius_km is not None:
                filters.append(distance <= search.radius_km)

        total = await self._session.scalar(
            select(func.count()).select_from(golf_courses_table).where(*filters)
        )

        # El id desempata siempre: sin un orden total, dos campos con la misma
        # distancia o el mismo nombre pueden salir en distinto orden en cada
        # consulta, y paginando eso significa ver uno repetido y perder otro.
        # Los 802 campos importados se dieron de alta en el mismo lote, así que
        # los empates no son hipotéticos
        #
        # Alfabético y no por fecha de alta: quien abre el desplegable busca un
        # campo que ya tiene en la cabeza, y lo recorre por su nombre. Ordenar
        # por `created_at` descendente hacía además que el lote de la RFEG,
        # importado de la A a la Z, saliera justo del revés
        stmt = select(GolfCourse).where(*filters)
        if distance is not None:
            stmt = stmt.add_columns(distance.label("distance_km")).order_by(
                distance.asc(), columns.id.asc()
            )
        else:
            stmt = stmt.order_by(columns.name.asc(), columns.id.asc())

        # selectinload y no joinedload: el join a las salidas multiplica las
        # filas, así que un LIMIT cortaría por la mitad las salidas de un campo
        # en vez de por el número de campos pedido
        stmt = stmt.options(selectinload(GolfCourse._tees))

        if search.offset:
            stmt = stmt.offset(search.offset)
        if search.limit is not None:
            stmt = stmt.limit(search.limit)

        result = await self._session.execute(stmt)

        courses: list[GolfCourse] = []
        distances: dict[str, float] = {}
        if distance is not None:
            for course, distance_km in result.all():
                courses.append(course)
                distances[str(course.id)] = round(float(distance_km), 3)
        else:
            courses = list(result.scalars().all())

        return ApprovedCoursePage(courses=courses, total=int(total or 0), distances_km=distances)

    async def find_pending_approval(self) -> list[GolfCourse]:
        """
        Busca todos los campos pendientes de aprobación.

        Returns:
            Lista de campos con status PENDING_APPROVAL
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
        stmt = (
            select(GolfCourse)
            .where(golf_courses_table.c.creator_id == creator_id)
            .options(
                joinedload(GolfCourse._tees),
            )
            .order_by(golf_courses_table.c.created_at.desc())
        )
        result = await self._session.execute(stmt)
        result = result.unique()
        return list(result.scalars().all())

    async def count_by_approval_status(self, approval_status: ApprovalStatus) -> int:
        """
        Cuenta campos de golf por estado de aprobación, sin materializarlos.

        Args:
            approval_status: Estado a contar (PENDING_APPROVAL, APPROVED, REJECTED)

        Returns:
            Número de campos con ese estado
        """
        stmt = (
            select(func.count())
            .select_from(golf_courses_table)
            .where(golf_courses_table.c.approval_status == approval_status)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def count_by_creator(self, creator_id: UserId) -> int:
        """
        Cuenta campos creados por un usuario específico, sin materializarlos.

        Args:
            creator_id: ID del creator

        Returns:
            Número de campos creados por ese usuario
        """
        stmt = (
            select(func.count())
            .select_from(golf_courses_table)
            .where(golf_courses_table.c.creator_id == creator_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete(self, golf_course_id: GolfCourseId) -> None:
        """
        Elimina un campo de golf (hard delete).

        Cascade delete automático con tees y holes (configurado en mapper).

        Args:
            golf_course_id: ID del campo a eliminar
        """
        golf_course = await self.find_by_id(golf_course_id)
        if golf_course:
            await self._session.delete(golf_course)
            await self._session.flush()
