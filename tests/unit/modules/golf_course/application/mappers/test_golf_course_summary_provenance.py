"""
La procedencia de un campo también viaja en los listados.

Hasta ahora solo la llevaba la ficha (`to_response_dto`): el frontend no podía
citar a la RFEG al elegir un campo en un listado (Crear competición), porque no
sabía de dónde venían sus datos. La cita de la fuente la pide la auditoría legal
del 20 oct 2026.
"""

from datetime import UTC, datetime

from src.modules.golf_course.application.mappers.golf_course_mapper import GolfCourseMapper
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_provenance import CourseProvenance
from src.modules.golf_course.domain.value_objects.course_source import CourseSource
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

IMPORTED_AT = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


def _course(
    provenance: CourseProvenance | None = None, physical_holes: int | None = None
) -> GolfCourse:
    return GolfCourse.create(
        name="Valderrama",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=[
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier=None,
                course_rating=71.2,
                slope_rating=128,
            )
        ],
        holes=[Hole(number=i + 1, par=4, stroke_index=i + 1, meters=350) for i in range(18)],
        provenance=provenance,
        physical_holes=physical_holes,
    )


def test_l1_the_list_item_carries_the_same_provenance_as_the_detail():
    """L1: el listado lleva `provenance` con la misma forma que la ficha."""
    course = _course(
        CourseProvenance(source=CourseSource.RFEG, external_id="915-1", imported_at=IMPORTED_AT)
    )

    summary = GolfCourseMapper.to_summary_dto(course)
    detail = GolfCourseMapper.to_response_dto(course)

    assert summary.provenance == detail.provenance


def test_l2_a_course_entered_by_hand_says_manual():
    """L2: un campo dado de alta a mano viaja como MANUAL, sin id externo."""
    summary = GolfCourseMapper.to_summary_dto(_course())

    assert summary.provenance.source == CourseSource.MANUAL
    assert summary.provenance.external_id is None


def test_l3_a_course_imported_from_the_rfeg_says_so():
    """L3: un campo de la RFEG viaja como RFEG con su id y su fecha de importación."""
    course = _course(
        CourseProvenance(source=CourseSource.RFEG, external_id="915-1", imported_at=IMPORTED_AT)
    )

    summary = GolfCourseMapper.to_summary_dto(course)

    assert summary.provenance.source == CourseSource.RFEG
    assert summary.provenance.external_id == "915-1"
    assert summary.provenance.imported_at == IMPORTED_AT


def test_l3b_the_provenance_is_serialised_in_the_list_json():
    """L3b: en el JSON del listado sale `provenance.source` como texto."""
    course = _course(
        CourseProvenance(source=CourseSource.RFEG, external_id="915-1", imported_at=IMPORTED_AT)
    )

    payload = GolfCourseMapper.to_summary_dto(course).model_dump(mode="json")

    assert payload["provenance"]["source"] == "RFEG"


def test_l5_the_detail_carries_the_provenance_too():
    """
    L5: la ficha también la lleva.

    El mapper ya se la pasaba, pero GolfCourseResponseDTO no declaraba el campo y
    Pydantic lo descartaba en silencio: la API no la enviaba en ningún sitio.
    """
    course = _course(
        CourseProvenance(source=CourseSource.RFEG, external_id="915-1", imported_at=IMPORTED_AT)
    )

    payload = GolfCourseMapper.to_response_dto(course).model_dump(mode="json")

    assert payload["provenance"]["source"] == "RFEG"
    assert payload["provenance"]["external_id"] == "915-1"


def test_l6_the_detail_carries_the_physical_holes_too():
    """
    L6: la ficha también lleva `physical_holes` (9 o 18 hoyos reales).

    Mismo fallo que la procedencia: el mapper lo pasaba, el DTO no lo declaraba y
    Pydantic lo descartaba.
    """
    nine = GolfCourseMapper.to_response_dto(_course(physical_holes=9)).model_dump(mode="json")
    unknown = GolfCourseMapper.to_response_dto(_course()).model_dump(mode="json")

    assert nine["physical_holes"] == 9
    # Un campo antiguo, del que no consta, viaja como null: el cliente distingue
    # «no se sabe» de un valor.
    assert unknown["physical_holes"] is None
