"""
Lo que lee el admin para revisar los hoyos (BE #575, 17 oct 2026).

- La lista: los campos con hoyos PENDIENTES, por nombre, y de cada hoyo, de menor
  a mayor, cuántas muestras tiene. Pendiente es con muestras y sin línea guardada:
  al guardarlo el admin, desaparece (Agustín, 17 oct); al reabrirlo, si conserva
  muestras, vuelve. `saved` sigue en la respuesta (siempre false) para no
  romper el contrato.
- Un campo (de los que ven los jugadores): sus 18 hoyos, cada uno con su línea guardada, TODAS sus muestras
  (con su id, para borrar las malas, y su barra) y los metros de cada barra en
  ese hoyo, para compararlos con lo que mide la línea.

Las muestras siguen siendo anónimas: no se guarda de quién son. Que quien llama
es admin lo mira la ruta.
"""

import unicodedata

from src.modules.golf_course.application.dtos.hole_review_dtos import (
    AdminHoleSampleDTO,
    GetHoleReviewRequestDTO,
    HoleReviewCountDTO,
    HoleReviewDTO,
    HoleReviewHoleDTO,
    HoleReviewSummaryDTO,
    ListHoleReviewsRequestDTO,
    ListHoleReviewsResponseDTO,
    TeeMetresDTO,
)
from src.modules.golf_course.application.exceptions import GolfCourseNotFoundError
from src.modules.golf_course.application.use_cases.hole_points import line_dto, point_dto, visible
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.hole_sample import HoleSample
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.mapped_hole import (
    MAX_HOLE_NUMBER,
    MIN_HOLE_NUMBER,
)


def _for_sorting(name: str) -> str:
    """El nombre sin mayúsculas ni acentos: el orden de un listado en castellano."""
    return "".join(
        c for c in unicodedata.normalize("NFD", name.casefold()) if not unicodedata.combining(c)
    )


class ListHoleReviewsUseCase:
    """Los campos con hoyos pendientes de revisar."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, request: ListHoleReviewsRequestDTO) -> ListHoleReviewsResponseDTO:
        async with self._uow:
            counts = await self._uow.hole_samples.count_by_hole()
            saved = await self._uow.saved_holes.list_all()
            samples: dict[GolfCourseId, dict[int, int]] = {}
            for course_id, hole, n in counts:
                samples.setdefault(course_id, {})[hole] = n
            saved_holes: dict[GolfCourseId, set[int]] = {}
            for line in saved:
                saved_holes.setdefault(line.golf_course_id, set()).add(line.hole_number)
            # Pendiente: con muestras (el recuento solo trae hoyos con alguna) y
            # sin línea guardada
            pending: dict[GolfCourseId, list[int]] = {}
            for course_id, holes in samples.items():
                kept = saved_holes.get(course_id, set())
                if left := sorted(hole for hole in holes if hole not in kept):
                    pending[course_id] = left
            course_ids = list(pending)
            # Solo los nombres, en una consulta: no cada campo con sus salidas
            names = await self._uow.golf_courses.find_names_by_ids(course_ids)
        courses = []
        for course_id in course_ids:
            name = names.get(str(course_id))
            if name is None:
                continue
            counted = samples[course_id]
            courses.append(
                HoleReviewSummaryDTO(
                    golf_course_id=str(course_id),
                    name=name,
                    holes=[
                        HoleReviewCountDTO(hole_number=hole, samples=counted[hole], saved=False)
                        for hole in pending[course_id]
                    ],
                )
            )
        courses.sort(key=lambda c: (_for_sorting(c.name), c.golf_course_id))
        return ListHoleReviewsResponseDTO(courses=courses)


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


def _cards(course: GolfCourse) -> list[tuple[Tee, dict[int, Hole]]]:
    """
    La tarjeta de cada barra, una vez: la suya (un campo dado de alta a mano
    copia la de referencia a las barras que no la traen, aceptado el 16 oct) y,
    si aun así no tiene, la de referencia.
    """
    cards = []
    for tee in course.tees:
        holes = tee.holes or course.hole_card_for(tee.color, tee.gender, tee.identifier)
        cards.append((tee, {h.number: h for h in holes}))
    return cards


def _tees(cards: list[tuple[Tee, dict[int, Hole]]], number: int) -> list[TeeMetresDTO]:
    """Lo que dice la tarjeta de cada barra en ese hoyo."""
    return [
        TeeMetresDTO(
            tee_color=tee.color,
            tee_gender=tee.gender,
            identifier=tee.identifier,
            par=card[number].par,
            meters=card[number].meters,
        )
        for tee, card in cards
        if number in card
    ]


class GetHoleReviewUseCase:
    """Los 18 hoyos de un campo, para revisarlos."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, request: GetHoleReviewRequestDTO) -> HoleReviewDTO:
        """
        Raises:
            GolfCourseNotFoundError: si el campo no existe o no lo ven los jugadores
        """
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            course = await self._uow.golf_courses.find_by_id(course_id)
            # Como al guardar: un campo que no ven los jugadores no lleva líneas
            if not visible(course):
                raise GolfCourseNotFoundError(request.golf_course_id)
            samples = await self._uow.hole_samples.list_by_course(course_id)
            saved = {
                h.hole_number: h for h in await self._uow.saved_holes.list_by_course(course_id)
            }
        by_hole: dict[int, list[HoleSample]] = {}
        for sample in samples:
            by_hole.setdefault(sample.hole_number, []).append(sample)
        cards = _cards(course)
        holes = []
        for number in range(MIN_HOLE_NUMBER, MAX_HOLE_NUMBER + 1):
            line = saved.get(number)
            holes.append(
                HoleReviewHoleDTO(
                    hole_number=number,
                    saved_line=line_dto(line.tee, line.bends, line.green_center) if line else None,
                    samples=[_sample_dto(x) for x in by_hole.get(number, [])],
                    tees=_tees(cards, number),
                )
            )
        return HoleReviewDTO(golf_course_id=str(course_id), name=course.name, holes=holes)
