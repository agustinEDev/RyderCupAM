"""
Las clasificaciones de un stroke play por casos de uso (#251, PR 5).

| Caso                                         | Resultado                                  |
|----------------------------------------------|--------------------------------------------|
| Franja: dos con hoyos validados              | Por puntos, con nombre, categoría y «tras» |
| Hoyos sin validar                            | No cuentan                                 |
| Franja filtrada por categoría                | Solo esa                                   |
| General acumulada en dos franjas             | Suma de las dos tarjetas                   |
| Hándicap distinto en cada franja             | Cuenta el de la última (P5)                |
| Scratch                                      | Puntos brutos, con la fila propia          |
| Una sesión que no es franja                  | PartidasError                              |
"""

from dataclasses import replace
from decimal import Decimal

import pytest

from src.modules.competition.application.exceptions import PartidasError
from src.modules.competition.application.use_cases.clasificaciones_use_case import (
    ClasificacionDeLaFranjaUseCase,
    ClasificacionGeneralUseCase,
    ClasificacionScratchUseCase,
)
from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_partida_repository import (
    InMemoryPartidaRepository,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    A_LAS_NUEVE_Y_CINCO,
)
from tests.unit.modules.competition.application.use_cases.test_entregar_tarjeta_de_partida_use_case import (
    _validar,
)
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    VIERNES,
    _Escenario,
)

pytestmark = pytest.mark.asyncio


async def _dos_franjas():
    """Mañana: A (3.0) y B (2.0). Tarde: A otra vez y C (9.0, otra categoría)."""
    escenario = _Escenario()
    await escenario.guardar()
    a = await escenario.con_plaza("3.0")
    b = await escenario.con_plaza("2.0")
    await escenario.generar()
    c = await escenario.con_plaza("19.0", franja=escenario.tarde)
    (suya,) = await escenario.uow.enrollments.find_by_user_ids_and_competition(
        [c], escenario.competicion.id
    )
    suya.congelar_handicap(Decimal("19.0"), 2)
    from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja

    async with escenario.uow:
        await escenario.uow.plazas.add(
            PlazaEnFranja.crear(
                escenario.competicion.id, escenario.tarde.id, a, A_LAS_NUEVE_Y_CINCO
            )
        )
    await escenario.generar(franja=escenario.tarde)
    return escenario, a, b, c


def _de_la_franja(escenario) -> ClasificacionDeLaFranjaUseCase:
    return ClasificacionDeLaFranjaUseCase(uow=escenario.uow, user_repository=escenario.usuarios)


def _general(escenario) -> ClasificacionGeneralUseCase:
    return ClasificacionGeneralUseCase(uow=escenario.uow, user_repository=escenario.usuarios)


def _scratch(escenario) -> ClasificacionScratchUseCase:
    return ClasificacionScratchUseCase(uow=escenario.uow, user_repository=escenario.usuarios)


async def _partida_de(escenario, franja, user_id):
    return next(
        p for p in await escenario.uow.partidas.de_la_franja(franja.id) if user_id in p.user_ids
    )


async def test_the_window_by_points_with_names_categories_and_thru():
    escenario, a, b, _ = await _dos_franjas()
    partida = await _partida_de(escenario, escenario.manana, a)
    await _validar(escenario, partida, a, hoyos=range(1, 3), golpes=4)  # 2 hoyos
    await _validar(escenario, partida, b, hoyos=range(1, 4), golpes=4)  # 3 hoyos

    tabla = await _de_la_franja(escenario).execute(escenario.manana.id.value)

    assert [(f.user_id, f.position, f.thru) for f in tabla.rows] == [
        (b.value, 1, 3),
        (a.value, 2, 2),
    ]
    assert tabla.rows[0].name == "Jugador 2.0"
    assert tabla.rows[0].category == 1
    assert (tabla.scale, tabla.tournament_type) == ("NETA", "STABLEFORD")


async def test_holes_not_validated_do_not_count():
    escenario, a, _, _ = await _dos_franjas()
    partida = await _partida_de(escenario, escenario.manana, a)
    golpe = GolpeDePartida.crear(
        partida.id, partida.round_id, partida.competition_id, a, 1, A_LAS_NUEVE_Y_CINCO
    )
    golpe.anotar_propio(4, True, a, A_LAS_NUEVE_Y_CINCO)
    await escenario.uow.golpes_de_partida.guardar(golpe)

    tabla = await _de_la_franja(escenario).execute(escenario.manana.id.value)

    assert {f.status for f in tabla.rows} == {"SIN_EMPEZAR"}


async def test_the_window_by_category():
    escenario, a, _, c = await _dos_franjas()
    partida = await _partida_de(escenario, escenario.tarde, c)
    await _validar(escenario, partida, a, hoyos=range(1, 2))
    await _validar(escenario, partida, c, hoyos=range(1, 2))

    tabla = await _de_la_franja(escenario).execute(escenario.tarde.id.value, categoria=2)

    assert [f.user_id for f in tabla.rows] == [c.value]


async def test_the_overall_adds_both_cards():
    escenario, a, b, _ = await _dos_franjas()
    manana = await _partida_de(escenario, escenario.manana, a)
    tarde = await _partida_de(escenario, escenario.tarde, a)
    await _validar(escenario, manana, a, hoyos=range(1, 3))
    await _validar(escenario, tarde, a, hoyos=range(1, 3))
    await _validar(escenario, manana, b, hoyos=range(1, 4))

    tabla = await _general(escenario).execute(escenario.competicion.id.value)

    suya = next(f for f in tabla.rows if f.user_id == a.value)
    assert (suya.cards, tabla.rule) == (2, "ACCUMULATED")


@pytest.mark.parametrize("al_reves", [False, True])
async def test_the_handicap_of_the_last_window(al_reves, monkeypatch):
    # El de desempatar (P5): antes salía el de la partida leída la última, y
    # se leen por el id de la franja, que no sigue el calendario. Se prueba en
    # los dos órdenes de lectura
    escenario, a, _, _ = await _dos_franjas()
    tarde = await _partida_de(escenario, escenario.tarde, a)
    tarde.recalcular(
        [replace(j, handicap=Decimal("1.0")) if j.user_id == a else j for j in tarde.jugadores]
    )
    await escenario.uow.partidas.guardar([tarde])
    leer = InMemoryPartidaRepository.de_la_competicion

    async def en_orden(self, competition_id):
        # La de la tarde leída la última, o la primera
        partidas = await leer(self, competition_id)
        return sorted(partidas, key=lambda p: (p.round_id == escenario.tarde.id) != al_reves)

    monkeypatch.setattr(InMemoryPartidaRepository, "de_la_competicion", en_orden)

    tabla = await _general(escenario).execute(escenario.competicion.id.value)

    assert next(f for f in tabla.rows if f.user_id == a.value).handicap == Decimal("1.0")


async def test_the_scratch_with_my_row():
    escenario, a, b, _ = await _dos_franjas()
    partida = await _partida_de(escenario, escenario.manana, a)
    await _validar(escenario, partida, a, hoyos=range(1, 3))

    tabla = await _scratch(escenario).execute(escenario.competicion.id.value, b)

    assert tabla.scale == "SCRATCH"
    assert [f.user_id for f in tabla.rows] == [a.value]
    # B no ha empezado: fuera de la tabla visible, su fila debajo y sin puesto
    assert (tabla.me.user_id, tabla.me.position) == (b.value, None)


async def test_a_session_that_is_not_a_window():
    escenario, _, _, _ = await _dos_franjas()
    sesion = Round.create(
        competition_id=escenario.competicion.id,
        golf_course_id=GolfCourseId.generate(),
        round_date=VIERNES,
        session_type=SessionType.EVENING,
        match_format=MatchFormat.SINGLES,
    )
    async with escenario.uow:
        await escenario.uow.rounds.add(sesion)

    with pytest.raises(PartidasError):
        await _de_la_franja(escenario).execute(sesion.id.value)
    with pytest.raises(PartidasError):
        await _de_la_franja(escenario).execute(RoundId.generate().value)
