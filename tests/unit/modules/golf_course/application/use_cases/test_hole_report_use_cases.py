"""
Tests de los casos de uso de los reportes de hoyo (entrega 7, aprobada el 18 oct 2026).

Un jugador reporta un hoyo mal con un motivo y la línea que propone. Como una
muestra: anónimo, el id lo pone el móvil y siempre se responde igual, se guarde
o no. El hoyo vuelve a «Pendientes» del admin; guardar su línea cierra sus
reportes y el admin puede descartar uno.

| Caso | Situación                                              | Resultado                                     |
|------|--------------------------------------------------------|-----------------------------------------------|
| A1   | Hoyo con línea guardada, reporte válido                | Se guarda, con su motivo y su línea           |
| A2   | Hoyo con línea de OSM aprobada                         | Se guarda                                     |
| A3   | Hoyo con una muestra completa                          | Se guarda                                     |
| A4   | Hoyo sin línea (nada, solo un green suelto, o el mapa sin aprobar) | No se guarda, sin error         |
| A5   | Cuarto reporte del hoyo                                | No se guarda (tres abiertos por hoyo)         |
| A6   | El mismo jugador antes de 10 min, y a los 10 min       | No se guarda; luego sí                        |
| A7   | Otro jugador, u otro hoyo                              | No les afecta la ventana                      |
| A8   | Reporte que el dominio rechaza (green a 800 m, 3 codos, lejos del campo) | No se guarda, no gasta ventana |
| A9   | El mismo id dos veces                                  | Cuenta uno, y el repetido no gasta ventana    |
| A10  | Falla la transacción                                   | No abre la ventana; el reintento se guarda    |
| A11  | Campo que no existe o pendiente; hoyo 0 o 19           | GolfCourseNotFoundError / HoleNotInCourseError |
| A12  | Los reportes no tocan lo que leen los jugadores        | La lectura de muestras no cambia              |
| A13  | El log al descartar                                    | Sin coordenadas ni quién lo mandó             |
| A14  | Respuesta                                              | Siempre SubmitHoleReportResponseDTO vacío     |
| D1   | El admin descarta un reporte                           | Se borra; los demás siguen                    |
| D2   | Descartar uno que no está en ese campo                 | HoleReportNotFoundError                       |
| D3   | Descartar en un campo que no existe                    | GolfCourseNotFoundError                       |
| S1   | El admin guarda la línea de un hoyo reportado          | Se cierran (borran) sus reportes, solo los de ese hoyo |
| S2   | El admin reabre un hoyo                                | Sus reportes no cambian                       |
| L1   | Lista: hoyo con línea guardada y un reporte            | Pendiente, con `reports=1` y sus muestras     |
| L2   | Lista: hoyo solo con reportes (línea de OSM)           | Pendiente, `samples=0`                        |
| L3   | Lista: hoyo con muestras y sin reportes                | `reports=0`                                   |
| L4   | Lista: el hoyo guardado sale al cerrarse sus reportes  | Ya no está                                    |
| G1   | Revisión del campo                                     | Cada hoyo con `reports` en orden de llegada (motivo, línea, día) |
| G2   | Hoyo sin reportes                                      | `reports=[]`                                  |
"""

import logging
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.modules.golf_course.application.dtos.hole_report_dtos import (
    DiscardHoleReportRequestDTO,
    SubmitHoleReportRequestDTO,
    SubmitHoleReportResponseDTO,
)
from src.modules.golf_course.application.dtos.hole_review_dtos import (
    GetHoleReviewRequestDTO,
    ListHoleReviewsRequestDTO,
)
from src.modules.golf_course.application.dtos.hole_sample_dtos import (
    ListHoleSamplesRequestDTO,
    PointDTO,
)
from src.modules.golf_course.application.dtos.saved_hole_dtos import (
    ReopenHoleRequestDTO,
    SaveHoleLineRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    GolfCourseNotFoundError,
    HoleNotInCourseError,
    HoleReportNotFoundError,
)
from src.modules.golf_course.application.use_cases.hole_report_use_cases import (
    DiscardHoleReportUseCase,
    SubmitHoleReportUseCase,
)
from src.modules.golf_course.application.use_cases.hole_review_use_cases import (
    GetHoleReviewUseCase,
    ListHoleReviewsUseCase,
)
from src.modules.golf_course.application.use_cases.hole_sample_use_cases import (
    ListHoleSamplesUseCase,
)
from src.modules.golf_course.application.use_cases.saved_hole_use_cases import (
    ReopenHoleUseCase,
    SaveHoleLineUseCase,
)
from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.hole_report import HoleReportReason
from src.modules.golf_course.domain.entities.hole_sample import HoleSample
from src.modules.golf_course.domain.entities.saved_hole import SavedHole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_location import CourseLocation
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.mapped_hole import MappedHole
from src.modules.golf_course.domain.value_objects.position_source import PositionSource
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.golf_course.infrastructure.services.in_memory_recent_hole_sample_senders import (
    InMemoryRecentHoleSampleSenders,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio

M_PER_DEGREE = 6_371_000.0 * 3.141592653589793 / 180
SALIDA = GeoPoint(latitude=36.28, longitude=-5.33)
VALDERRAMA = CourseLocation(latitude=36.285, longitude=-5.33)
JUGADOR = str(uuid4())


def _north(metres: float, of: GeoPoint = SALIDA) -> GeoPoint:
    return GeoPoint(latitude=of.latitude + metres / M_PER_DEGREE, longitude=of.longitude)


GREEN = _north(300)


def _p(point: GeoPoint) -> PointDTO:
    return PointDTO(latitude=point.latitude, longitude=point.longitude)


def _course(approved=True) -> GolfCourse:
    course = GolfCourse.create(
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
        location=VALDERRAMA,
    )
    if approved:
        course.approve()
    return course


class Reloj:
    """Un reloj que solo avanza cuando el test lo pide."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class UoWQueFallaAlConfirmar(InMemoryGolfCourseUnitOfWork):
    """La transacción falla al confirmar las veces que se pida."""

    def __init__(self) -> None:
        super().__init__()
        self.failures = 0

    async def commit(self) -> None:
        if self.failures:
            self.failures -= 1
            raise RuntimeError("commit failed")
        await super().commit()


def _saved(course, hole=1) -> SavedHole:
    return SavedHole.create(
        golf_course_id=course.id,
        hole_number=hole,
        tee=SALIDA,
        bends=(),
        green_center=GREEN,
        saved_by=UserId.generate(),
        course_location=None,
    )


def _sample(course, hole=1, tee=SALIDA) -> HoleSample:
    return HoleSample.create(
        id=uuid4(),
        golf_course_id=course.id,
        hole_number=hole,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        tee=tee,
        bends=(),
        green_center=GREEN,
        course_location=None,
    )


def _osm_map(course, hole=1, approved=True) -> CourseHoleMap:
    factory = CourseHoleMap.create_approved if approved else CourseHoleMap.create
    return factory(
        golf_course_id=course.id,
        holes=[MappedHole(number=hole, play_line=(SALIDA, GREEN), line_source=PositionSource.OSM)],
        osm_reference="way/1",
        imported_at=datetime(2026, 10, 18, 9, 0),
    )


async def _setup(uow=None, line="saved", hole=1):
    """Un campo con el hoyo `hole` con línea: guardada, de OSM, o de una muestra."""
    uow = uow or InMemoryGolfCourseUnitOfWork()
    uow.reloj = Reloj()
    uow.senders = InMemoryRecentHoleSampleSenders(clock=uow.reloj)
    course = _course()
    await uow.golf_courses.save(course)
    if line == "saved":
        await uow.saved_holes.save(_saved(course, hole))
    elif line == "osm":
        await uow.hole_maps.save(_osm_map(course, hole))
    elif line == "sample":
        await uow.hole_samples.add(_sample(course, hole))
    return uow, course


def _request(course, hole=1, user=None, report_id=None, green=GREEN, bends=(), reason=None):
    return SubmitHoleReportRequestDTO(
        id=report_id or uuid4(),
        golf_course_id=str(course.id if hasattr(course, "id") else course),
        hole_number=hole,
        user_id=user or str(uuid4()),
        reason=reason or HoleReportReason.WRONG_LINE,
        tee=_p(SALIDA),
        bends=[_p(b) for b in bends],
        green_center=_p(green),
    )


async def _submit(uow, course, **kwargs) -> None:
    result = await SubmitHoleReportUseCase(uow, uow.senders).execute(_request(course, **kwargs))
    assert result == SubmitHoleReportResponseDTO()


async def _stored(uow, course, hole=1) -> int:
    return await uow.hole_reports.count_for_hole(course.id, hole)


# ============================================================================
# A — Mandar
# ============================================================================


@pytest.mark.parametrize("line", ["saved", "osm", "sample"])
async def test_a1_a3_a_report_on_a_hole_with_a_line_is_stored(line):
    """
    GIVEN: Un hoyo con línea guardada, de OSM aprobada o de una muestra completa
    WHEN: Un jugador lo reporta con su motivo y su línea
    THEN: Se guarda, con su motivo, su línea y el día UTC
    """
    uow, course = await _setup(line=line)
    report_id = uuid4()

    await _submit(
        uow, course, report_id=report_id, bends=[_north(150)], reason=HoleReportReason.HOLE_CHANGED
    )

    [report] = await uow.hole_reports.list_by_course(course.id)
    assert report.id == report_id
    assert report.reason is HoleReportReason.HOLE_CHANGED
    assert report.tee == SALIDA
    assert report.bends == (_north(150),)
    assert report.green_center == GREEN
    assert report.received_on == datetime.now(UTC).date()


@pytest.mark.parametrize("line", ["none", "green-only", "osm-pending"])
async def test_a4_a_hole_without_a_line_is_not_reported(line):
    """
    GIVEN: Un hoyo sin línea: nada, solo un green suelto, o un mapa de OSM sin aprobar
    WHEN: Llega un reporte
    THEN: No se guarda, sin error, y no gasta la ventana del jugador
    """
    uow, course = await _setup(line="none")
    if line == "green-only":
        await uow.hole_samples.add(_sample(course, tee=None))
    elif line == "osm-pending":
        await uow.hole_maps.save(_osm_map(course, approved=False))

    await _submit(uow, course, user=JUGADOR)

    assert await _stored(uow, course) == 0
    # Con línea guardada después, el mismo jugador sí puede
    await uow.saved_holes.save(_saved(course))
    await _submit(uow, course, user=JUGADOR)
    assert await _stored(uow, course) == 1


async def test_a5_at_most_three_open_reports_per_hole():
    """
    GIVEN: Un hoyo con tres reportes abiertos
    WHEN: Llega un cuarto (de otro jugador)
    THEN: No se guarda; otro hoyo sigue recogiendo
    """
    uow, course = await _setup()
    await uow.saved_holes.save(_saved(course, hole=2))
    for _ in range(4):
        await _submit(uow, course)

    await _submit(uow, course, hole=2)

    assert await _stored(uow, course) == 3
    assert await _stored(uow, course, hole=2) == 1


async def test_a6_one_report_per_player_and_hole_every_10_minutes():
    """
    GIVEN: Un jugador que ya reportó el hoyo
    WHEN: Vuelve a reportarlo a los 599 s, y a los 600 s
    THEN: El primero no se guarda; el segundo sí
    """
    uow, course = await _setup()
    await _submit(uow, course, user=JUGADOR)

    uow.reloj.now += 599
    await _submit(uow, course, user=JUGADOR)
    assert await _stored(uow, course) == 1

    uow.reloj.now += 1
    await _submit(uow, course, user=JUGADOR)
    assert await _stored(uow, course) == 2


async def test_a7_the_window_is_per_player_and_hole():
    """
    GIVEN: Un jugador que acaba de reportar el hoyo 1
    WHEN: Otro jugador reporta el 1 y el mismo reporta el 2
    THEN: Se guardan los dos
    """
    uow, course = await _setup()
    await uow.saved_holes.save(_saved(course, hole=2))
    await _submit(uow, course, user=JUGADOR)

    await _submit(uow, course)
    await _submit(uow, course, user=JUGADOR, hole=2)

    assert await _stored(uow, course) == 2
    assert await _stored(uow, course, hole=2) == 1


@pytest.mark.parametrize(
    "malo",
    [
        {"green": _north(800)},
        {"bends": [_north(50), _north(100), _north(150)]},
        {"bends": [_north(5000)]},
    ],
    ids=["green-a-800-m", "tres-codos", "lejos-del-campo"],
)
async def test_a8_an_invalid_report_is_dropped_and_spends_no_window(malo):
    """
    GIVEN: Un reporte que el dominio rechaza
    WHEN: Llega
    THEN: No se guarda, sin error; el siguiente bueno del mismo jugador sí
    """
    uow, course = await _setup()

    await _submit(uow, course, user=JUGADOR, **malo)
    assert await _stored(uow, course) == 0

    await _submit(uow, course, user=JUGADOR)
    assert await _stored(uow, course) == 1


async def test_a9_the_same_id_counts_once_and_spends_no_window():
    """
    GIVEN: Un reporte ya guardado
    WHEN: Llega otra vez el mismo id, de otro jugador, y luego uno nuevo suyo
    THEN: El repetido no cuenta ni gasta su ventana; el nuevo se guarda
    """
    uow, course = await _setup()
    report_id = uuid4()
    await _submit(uow, course, report_id=report_id)

    await _submit(uow, course, report_id=report_id, user=JUGADOR)
    assert await _stored(uow, course) == 1

    await _submit(uow, course, user=JUGADOR)
    assert await _stored(uow, course) == 2


async def test_a10_a_failed_transaction_opens_no_window():
    """
    GIVEN: La transacción falla al confirmar
    WHEN: El jugador reintenta enseguida
    THEN: El reintento se guarda (la ventana no se abrió)
    """
    uow, course = await _setup(uow=UoWQueFallaAlConfirmar())
    uow.failures = 1

    with pytest.raises(RuntimeError):
        await SubmitHoleReportUseCase(uow, uow.senders).execute(_request(course, user=JUGADOR))
    # En memoria no hay vuelta atrás: lo que se mira es que el reintento entra
    antes = await _stored(uow, course)
    await _submit(uow, course, user=JUGADOR)

    assert await _stored(uow, course) == antes + 1


async def test_a11_unknown_or_pending_course_and_bad_hole():
    """
    GIVEN: Un campo que no existe, uno pendiente, y un hoyo 0 o 19
    WHEN: Llega un reporte
    THEN: GolfCourseNotFoundError, y HoleNotInCourseError
    """
    uow, course = await _setup()
    pendiente = _course(approved=False)
    await uow.golf_courses.save(pendiente)
    use_case = SubmitHoleReportUseCase(uow, uow.senders)

    for missing in (str(uuid4()), str(pendiente.id)):
        with pytest.raises(GolfCourseNotFoundError):
            await use_case.execute(_request(missing))
    for hole in (0, 19):
        with pytest.raises(HoleNotInCourseError):
            await use_case.execute(_request(course, hole=hole))


async def test_a12_reports_do_not_change_what_players_read():
    """
    GIVEN: Un hoyo con línea guardada
    WHEN: Se reporta
    THEN: La lectura de los jugadores es la misma que antes
    """
    uow, course = await _setup()
    leer = ListHoleSamplesUseCase(uow)
    antes = await leer.execute(ListHoleSamplesRequestDTO(golf_course_id=str(course.id)))

    await _submit(uow, course)

    assert await leer.execute(ListHoleSamplesRequestDTO(golf_course_id=str(course.id))) == antes


async def test_a13_the_log_says_neither_coordinates_nor_who(caplog):
    """
    GIVEN: Reportes que se descartan (hoyo sin línea, y ventana)
    WHEN: Se escribe el log
    THEN: No lleva coordenadas ni el id del jugador
    """
    uow, course = await _setup()
    caplog.set_level(logging.DEBUG)

    await _submit(uow, course, hole=5, user=JUGADOR)
    await _submit(uow, course, user=JUGADOR)
    await _submit(uow, course, user=JUGADOR)

    texto = caplog.text
    assert texto
    assert JUGADOR not in texto
    assert "36.28" not in texto and "-5.33" not in texto


# ============================================================================
# D — Descartar
# ============================================================================


async def test_d1_the_admin_discards_one_report():
    """
    GIVEN: Un hoyo con dos reportes
    WHEN: El admin descarta uno
    THEN: Se borra ese y el otro sigue
    """
    uow, course = await _setup()
    uno, otro = uuid4(), uuid4()
    await _submit(uow, course, report_id=uno)
    await _submit(uow, course, report_id=otro)

    await DiscardHoleReportUseCase(uow).execute(
        DiscardHoleReportRequestDTO(golf_course_id=str(course.id), report_id=uno)
    )

    assert [r.id for r in await uow.hole_reports.list_by_course(course.id)] == [otro]


async def test_d2_a_report_of_another_course_is_not_found():
    """
    GIVEN: Un reporte de un campo
    WHEN: Se descarta en otro campo, o uno que no existe
    THEN: HoleReportNotFoundError, y el reporte sigue
    """
    uow, course = await _setup()
    otro_campo = _course()
    await uow.golf_courses.save(otro_campo)
    report_id = uuid4()
    await _submit(uow, course, report_id=report_id)
    use_case = DiscardHoleReportUseCase(uow)

    for campo, rid in ((otro_campo, report_id), (course, uuid4())):
        with pytest.raises(HoleReportNotFoundError):
            await use_case.execute(
                DiscardHoleReportRequestDTO(golf_course_id=str(campo.id), report_id=rid)
            )
    assert await _stored(uow, course) == 1


async def test_d3_discarding_in_an_unknown_course():
    """
    GIVEN: Un campo que no existe
    WHEN: Se descarta un reporte en él
    THEN: GolfCourseNotFoundError
    """
    uow, _ = await _setup()

    with pytest.raises(GolfCourseNotFoundError):
        await DiscardHoleReportUseCase(uow).execute(
            DiscardHoleReportRequestDTO(golf_course_id=str(uuid4()), report_id=uuid4())
        )


# ============================================================================
# S — Guardar la línea cierra los reportes; reabrir no
# ============================================================================


async def test_s1_saving_the_line_closes_the_hole_reports():
    """
    GIVEN: Dos reportes en el hoyo 1 y uno en el 2
    WHEN: El admin guarda la línea del 1
    THEN: Los del 1 se cierran y el del 2 sigue
    """
    uow, course = await _setup()
    await uow.saved_holes.save(_saved(course, hole=2))
    await _submit(uow, course)
    await _submit(uow, course)
    await _submit(uow, course, hole=2)

    await SaveHoleLineUseCase(uow).execute(
        SaveHoleLineRequestDTO(
            golf_course_id=str(course.id),
            hole_number=1,
            admin_id=str(UserId.generate()),
            tee=_p(SALIDA),
            bends=[],
            green_center=_p(_north(320)),
        )
    )

    assert await _stored(uow, course) == 0
    assert await _stored(uow, course, hole=2) == 1


async def test_s2_reopening_a_hole_keeps_its_reports():
    """
    GIVEN: Un hoyo guardado con un reporte
    WHEN: El admin lo reabre
    THEN: El reporte sigue
    """
    uow, course = await _setup()
    await _submit(uow, course)

    await ReopenHoleUseCase(uow).execute(
        ReopenHoleRequestDTO(golf_course_id=str(course.id), hole_number=1)
    )

    assert await _stored(uow, course) == 1


# ============================================================================
# L, G — Lo que lee el admin
# ============================================================================


async def _list(uow):
    return (await ListHoleReviewsUseCase(uow).execute(ListHoleReviewsRequestDTO())).courses


async def test_l1_l3_pending_holes_say_their_reports():
    """
    GIVEN: El hoyo 1 guardado, con una muestra y un reporte; el 4 con una muestra
    WHEN: Se lee la lista
    THEN: El 1 está pendiente con reports=1 y samples=1; el 4 con reports=0
    """
    uow, course = await _setup()
    await uow.hole_samples.add(_sample(course, hole=1))
    await uow.hole_samples.add(_sample(course, hole=4))
    await _submit(uow, course)

    [campo] = await _list(uow)

    assert [(h.hole_number, h.samples, h.reports) for h in campo.holes] == [(1, 1, 1), (4, 1, 0)]
    # `saved` dice la verdad: el 1 tiene línea guardada, aunque esté pendiente
    # por su reporte (/code-review, 18 oct)
    assert [h.model_dump()["saved"] for h in campo.holes] == [True, False]


async def test_l2_a_hole_with_only_reports_is_pending():
    """
    GIVEN: Un hoyo con línea de OSM, sin muestras, con un reporte
    WHEN: Se lee la lista
    THEN: Está pendiente, con samples=0 y reports=1
    """
    uow, course = await _setup(line="osm")
    await _submit(uow, course)

    [campo] = await _list(uow)

    assert [(h.hole_number, h.samples, h.reports) for h in campo.holes] == [(1, 0, 1)]


async def test_l4_saving_the_reported_hole_takes_it_off_the_list():
    """
    GIVEN: Un hoyo de OSM con un reporte (pendiente)
    WHEN: El admin guarda su línea
    THEN: Sale de la lista
    """
    uow, course = await _setup(line="osm")
    await _submit(uow, course)

    await SaveHoleLineUseCase(uow).execute(
        SaveHoleLineRequestDTO(
            golf_course_id=str(course.id),
            hole_number=1,
            admin_id=str(UserId.generate()),
            tee=_p(SALIDA),
            bends=[],
            green_center=_p(GREEN),
        )
    )

    assert await _list(uow) == []


async def test_g1_g2_the_review_brings_each_hole_reports_in_arrival_order():
    """
    GIVEN: Dos reportes en el hoyo 1, el segundo con un codo
    WHEN: Se lee la revisión del campo
    THEN: El 1 los trae en orden (id, motivo, línea, día); el 2, ninguno
    """
    uow, course = await _setup()
    uno, otro = uuid4(), uuid4()
    await _submit(uow, course, report_id=uno, reason=HoleReportReason.WRONG_HOLE)
    await _submit(uow, course, report_id=otro, bends=[_north(150)])

    review = await GetHoleReviewUseCase(uow).execute(
        GetHoleReviewRequestDTO(golf_course_id=str(course.id))
    )

    primero, segundo = review.holes[0].reports
    assert (primero.id, primero.reason) == (uno, HoleReportReason.WRONG_HOLE)
    assert primero.tee == _p(SALIDA)
    assert primero.bends == []
    assert primero.green_center == _p(GREEN)
    assert primero.received_on == datetime.now(UTC).date()
    assert (segundo.id, segundo.bends) == (otro, [_p(_north(150))])
    assert review.holes[1].reports == []
