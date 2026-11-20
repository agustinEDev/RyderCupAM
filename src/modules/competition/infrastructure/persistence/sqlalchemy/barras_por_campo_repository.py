"""Los cambios de barras por campo, en Postgres (barras por campo, 20 nov 2026)."""

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.repositories.barras_por_campo_repository_interface import (
    BarrasPorCampoRepositoryInterface,
)
from src.modules.competition.domain.value_objects.barras_del_campo import BarrasDelCampo
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    competition_course_tees_table,
    enrollment_course_tees_table,
    enrollments_table,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.services.instante_utc import ahora_en_utc
from src.shared.domain.value_objects.gender import Gender


class SQLAlchemyBarrasPorCampoRepository(BarrasPorCampoRepositoryInterface):
    """Una fila por cambio; quitar un cambio es borrar su fila."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def del_campo(
        self, competition_id: CompetitionId, golf_course_id: GolfCourseId
    ) -> BarrasDelCampo:
        propias = enrollment_course_tees_table
        inscripciones = enrollments_table
        filas_propias = (
            await self._session.execute(
                select(inscripciones.c.user_id, propias.c.tee_color)
                .join(inscripciones, inscripciones.c.id == propias.c.enrollment_id)
                .where(
                    inscripciones.c.competition_id == competition_id,
                    propias.c.golf_course_id == golf_course_id,
                    # Solo las de inscripciones aprobadas: una retirada no juega
                    inscripciones.c.status == EnrollmentStatus.APPROVED.value,
                )
            )
        ).all()
        del_campo = competition_course_tees_table
        filas_del_campo = (
            await self._session.execute(
                select(del_campo.c.gender, del_campo.c.tee_color).where(
                    del_campo.c.competition_id == competition_id,
                    del_campo.c.golf_course_id == golf_course_id,
                )
            )
        ).all()
        return BarrasDelCampo(
            propias={fila.user_id: TeeColor(fila.tee_color) for fila in filas_propias},
            por_genero={Gender(fila.gender): TeeColor(fila.tee_color) for fila in filas_del_campo},
        )

    async def fijar_propia(
        self, enrollment: Enrollment, golf_course_id: GolfCourseId, tee_color: TeeColor | None
    ) -> None:
        tabla = enrollment_course_tees_table
        if tee_color is None:
            await self._session.execute(
                delete(tabla).where(
                    tabla.c.enrollment_id == enrollment.id,
                    tabla.c.golf_course_id == golf_course_id,
                )
            )
            return
        fila = insert(tabla).values(
            enrollment_id=enrollment.id,
            golf_course_id=golf_course_id,
            tee_color=tee_color.value,
            updated_at=ahora_en_utc(),
        )
        await self._session.execute(
            fila.on_conflict_do_update(
                index_elements=[tabla.c.enrollment_id, tabla.c.golf_course_id],
                set_={"tee_color": fila.excluded.tee_color, "updated_at": fila.excluded.updated_at},
            )
        )

    async def fijar_del_campo(
        self,
        competition_id: CompetitionId,
        golf_course_id: GolfCourseId,
        genero: Gender,
        tee_color: TeeColor | None,
    ) -> None:
        tabla = competition_course_tees_table
        if tee_color is None:
            await self._session.execute(
                delete(tabla).where(
                    tabla.c.competition_id == competition_id,
                    tabla.c.golf_course_id == golf_course_id,
                    tabla.c.gender == genero.value,
                )
            )
            return
        fila = insert(tabla).values(
            competition_id=competition_id,
            golf_course_id=golf_course_id,
            gender=genero.value,
            tee_color=tee_color.value,
            updated_at=ahora_en_utc(),
        )
        await self._session.execute(
            fila.on_conflict_do_update(
                index_elements=[tabla.c.competition_id, tabla.c.golf_course_id, tabla.c.gender],
                set_={"tee_color": fila.excluded.tee_color, "updated_at": fila.excluded.updated_at},
            )
        )

    async def borrar_del_campo(
        self, competition_id: CompetitionId, golf_course_id: GolfCourseId
    ) -> None:
        del_campo = competition_course_tees_table
        await self._session.execute(
            delete(del_campo).where(
                del_campo.c.competition_id == competition_id,
                del_campo.c.golf_course_id == golf_course_id,
            )
        )
        propias = enrollment_course_tees_table
        de_la_competicion = select(enrollments_table.c.id).where(
            enrollments_table.c.competition_id == competition_id
        )
        await self._session.execute(
            delete(propias).where(
                propias.c.golf_course_id == golf_course_id,
                propias.c.enrollment_id.in_(de_la_competicion),
            )
        )

    async def borrar_propias(self, enrollment: Enrollment) -> None:
        tabla = enrollment_course_tees_table
        await self._session.execute(delete(tabla).where(tabla.c.enrollment_id == enrollment.id))
