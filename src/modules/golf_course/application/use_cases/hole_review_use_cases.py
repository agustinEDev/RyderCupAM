"""
Lo que lee el admin para revisar los hoyos (BE #575, 17 oct 2026).

- La lista: los campos con hoyos por revisar (con muestras o con su línea ya
  guardada), por nombre, y de cada hoyo cuántas muestras tiene y si está guardado.
- Un campo: sus 18 hoyos, cada uno con su línea guardada, TODAS sus muestras
  (con su id, para borrar las malas, y su barra) y los metros de cada barra en
  ese hoyo, para compararlos con lo que mide la línea.

Las muestras siguen siendo anónimas: no se guarda de quién son. Que quien llama
es admin lo mira la ruta.
"""

from src.modules.golf_course.application.dtos.hole_review_dtos import (
    AdminHoleSampleDTO,
    GetHoleReviewRequestDTO,
    HoleReviewCountDTO,
    HoleReviewDTO,
    HoleReviewHoleDTO,
    HoleReviewSummaryDTO,
    ListHoleReviewsResponseDTO,
    TeeMetresDTO,
)
from src.modules.golf_course.application.exceptions import GolfCourseNotFoundError
from src.modules.golf_course.application.use_cases.hole_points import line_dto, point_dto
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole_sample import HoleSample
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.mapped_hole import (
    MAX_HOLE_NUMBER,
    MIN_HOLE_NUMBER,
)


class ListHoleReviewsUseCase:
    """Los campos con hoyos por revisar."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self) -> ListHoleReviewsResponseDTO:
        async with self._uow:
            counts = await self._uow.hole_samples.count_by_hole()
            saved = await self._uow.saved_holes.list_all()
            by_course: dict[GolfCourseId, dict[int, list]] = {}
            for course_id, hole, n in counts:
                by_course.setdefault(course_id, {}).setdefault(hole, [0, False])[0] = n
            for line in saved:
                by_course.setdefault(line.golf_course_id, {}).setdefault(
                    line.hole_number, [0, False]
                )[1] = True
            courses = []
            for course_id, holes in by_course.items():
                course = await self._uow.golf_courses.find_by_id(course_id)
                if course is None:
                    continue
                courses.append(
                    HoleReviewSummaryDTO(
                        golf_course_id=str(course_id),
                        name=course.name,
                        holes=[
                            HoleReviewCountDTO(hole_number=hole, samples=n, saved=is_saved)
                            for hole, (n, is_saved) in sorted(holes.items())
                        ],
                    )
                )
        return ListHoleReviewsResponseDTO(courses=sorted(courses, key=lambda c: c.name))


def _sample_dto(sample: HoleSample) -> AdminHoleSampleDTO:
    return AdminHoleSampleDTO(
        id=sample.id,
        tee_color=sample.tee_color,
        tee_gender=sample.tee_gender,
        tee=point_dto(sample.tee) if sample.tee else None,
        bends=[point_dto(bend) for bend in sample.bends],
        green_center=point_dto(sample.green_center),
        received_on=sample.received_on,
    )


def _tees(course: GolfCourse, number: int) -> list[TeeMetresDTO]:
    """La tarjeta de cada barra en ese hoyo, como se juega desde ella."""
    tees = []
    for tee in course.tees:
        card = {h.number: h for h in course.hole_card_for(tee.color, tee.gender, tee.identifier)}
        hole = card.get(number)
        if hole is None:
            continue
        tees.append(
            TeeMetresDTO(
                tee_color=tee.color,
                tee_gender=tee.gender,
                identifier=tee.identifier,
                par=hole.par,
                meters=hole.meters,
            )
        )
    return tees


class GetHoleReviewUseCase:
    """Los 18 hoyos de un campo, para revisarlos."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, request: GetHoleReviewRequestDTO) -> HoleReviewDTO:
        """
        Raises:
            GolfCourseNotFoundError: si el campo no existe
        """
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            course = await self._uow.golf_courses.find_by_id(course_id)
            if course is None:
                raise GolfCourseNotFoundError(request.golf_course_id)
            samples = await self._uow.hole_samples.list_by_course(course_id)
            saved = {
                h.hole_number: h for h in await self._uow.saved_holes.list_by_course(course_id)
            }
        by_hole: dict[int, list[HoleSample]] = {}
        for sample in samples:
            by_hole.setdefault(sample.hole_number, []).append(sample)
        holes = []
        for number in range(MIN_HOLE_NUMBER, MAX_HOLE_NUMBER + 1):
            line = saved.get(number)
            holes.append(
                HoleReviewHoleDTO(
                    hole_number=number,
                    saved_line=line_dto(line.tee, line.bends, line.green_center) if line else None,
                    samples=[_sample_dto(x) for x in by_hole.get(number, [])],
                    tees=_tees(course, number),
                )
            )
        return HoleReviewDTO(golf_course_id=str(course_id), name=course.name, holes=holes)
