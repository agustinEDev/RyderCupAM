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
| Retirado en Stableford                       | Cuenta lo jugado, `retired` (QA 11 oct)    |
| Género de sus barras en cada fila            | «No presentada», «Retirada» (#856)         |
"""

from dataclasses import replace
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.exceptions import PartidasError
from src.modules.competition.application.services.lo_jugado_de_una_privada import NoPuedeVerloError
from src.modules.competition.application.use_cases.clasificaciones_use_case import (
    ClasificacionDeLaFranjaUseCase,
    ClasificacionGeneralUseCase,
    ClasificacionScratchUseCase,
)
from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_partida_repository import (
    InMemoryPartidaRepository,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
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


async def test_a_stableford_withdrawal_counts_and_says_so():
    escenario, a, b, _ = await _dos_franjas()
    partida = await _partida_de(escenario, escenario.manana, a)
    await _validar(escenario, partida, a, hoyos=range(1, 3), golpes=4)
    await _validar(escenario, partida, b, hoyos=range(1, 4), golpes=4)
    partida = await _partida_de(escenario, escenario.manana, a)
    partida.empezar()
    partida.retirar(a)
    await escenario.uow.partidas.guardar([partida])

    tabla = await _de_la_franja(escenario).execute(escenario.manana.id.value)

    assert [(f.user_id, f.retired, f.status) for f in tabla.rows] == [
        (b.value, False, "CLASIFICADO"),
        (a.value, True, "CLASIFICADO"),
    ]


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


async def _ella_es(escenario, user_id):
    """Barras de mujer en todas sus partidas."""
    for franja in (escenario.manana, escenario.tarde):
        for partida in await escenario.uow.partidas.de_la_franja(franja.id):
            if user_id in partida.user_ids:
                partida.recalcular(
                    [
                        replace(j, tee_gender=Gender.FEMALE) if j.user_id == user_id else j
                        for j in partida.jugadores
                    ]
                )
                await escenario.uow.partidas.guardar([partida])


@pytest.mark.parametrize("cual", ["franja", "general", "scratch"])
async def test_each_row_carries_the_gender_of_its_tees(cual):
    escenario, a, b, c = await _dos_franjas()
    await _ella_es(escenario, b)
    partida = await _partida_de(escenario, escenario.manana, a)
    await _validar(escenario, partida, a, hoyos=range(1, 3))
    await _validar(escenario, partida, b, hoyos=range(1, 3))

    if cual == "franja":
        tabla = await _de_la_franja(escenario).execute(escenario.manana.id.value)
    elif cual == "general":
        tabla = await _general(escenario).execute(escenario.competicion.id.value)
    else:
        # C no ha empezado: su fila va aparte, en `me`
        tabla = await _scratch(escenario).execute(escenario.competicion.id.value, c)

    generos = {f.user_id: f.tee_gender for f in tabla.rows}
    assert generos[a.value] == "MALE"
    assert generos[b.value] == "FEMALE"
    if cual == "scratch":
        assert (tabla.me.user_id, tabla.me.tee_gender) == (c.value, "MALE")


@pytest.mark.parametrize(
    ("manana", "tarde", "esperado"),
    [
        (Gender.FEMALE, Gender.MALE, "MALE"),
        (Gender.MALE, Gender.FEMALE, "FEMALE"),
        # Sin dato en la última, el último conocido (/code-review)
        (Gender.FEMALE, None, "FEMALE"),
        (None, None, None),
    ],
)
async def test_the_gender_is_the_one_of_the_last_group(manana, tarde, esperado):
    escenario, a, _, _ = await _dos_franjas()
    for franja, genero in ((escenario.manana, manana), (escenario.tarde, tarde)):
        partida = await _partida_de(escenario, franja, a)
        partida.recalcular(
            [replace(j, tee_gender=genero) if j.user_id == a else j for j in partida.jugadores]
        )
        await escenario.uow.partidas.guardar([partida])

    tabla = await _general(escenario).execute(escenario.competicion.id.value)

    assert next(f for f in tabla.rows if f.user_id == a.value).tee_gender == esperado


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


# --- Quién las ve, dentro del caso de uso (tabla del 27 oct 2026; PR 2, R7) --------


class _Eventos:
    def __init__(self, *amigos):
        self.amigos = frozenset(amigos)

    async def amigos_con_evento_en(self, user_id, competition_id):
        return self.amigos


def _las_tres(escenario, eventos):
    deps = {"uow": escenario.uow, "user_repository": escenario.usuarios, "eventos": eventos}
    return {
        "franja": lambda quien, **kw: ClasificacionDeLaFranjaUseCase(**deps).execute(
            escenario.manana.id.value, quien=quien, **kw
        ),
        "general": lambda quien, **kw: ClasificacionGeneralUseCase(**deps).execute(
            escenario.competicion.id.value, quien=quien, **kw
        ),
        "scratch": lambda quien, **kw: ClasificacionScratchUseCase(**deps).execute(
            escenario.competicion.id.value, quien, **kw
        ),
    }


@pytest.mark.parametrize("cual", ["franja", "general", "scratch"])
async def test_6_de_fuera_de_una_privada_no_la_ve(cual):
    escenario, _, _, _ = await _dos_franjas()

    with pytest.raises(NoPuedeVerloError):
        await _las_tres(escenario, _Eventos())[cual](UserId(uuid4()))


@pytest.mark.parametrize("cual", ["franja", "general", "scratch"])
async def test_7_con_la_llave_entera(cual):
    escenario, a, b, _ = await _dos_franjas()

    con_llave = await _las_tres(escenario, _Eventos(a))[cual](UserId(uuid4()))
    dentro = await _las_tres(escenario, _Eventos())[cual](b)

    # La misma tabla que quien está dentro: entera, no solo su amigo
    assert [r.user_id for r in con_llave.rows] == [r.user_id for r in dentro.rows]


@pytest.mark.parametrize("cual", ["franja", "general", "scratch"])
async def test_dentro_la_ve(cual):
    escenario, a, _, _ = await _dos_franjas()

    await _las_tres(escenario, _Eventos())[cual](a)
    await _las_tres(escenario, _Eventos())[cual](escenario.creador)
    await _las_tres(escenario, _Eventos())[cual](UserId(uuid4()), es_admin=True)


async def test_sin_decir_quien_mira_va_entera():
    """Los usos internos leen la general sin puerta."""
    escenario, a, _, _ = await _dos_franjas()

    tabla = await ClasificacionGeneralUseCase(
        uow=escenario.uow, user_repository=escenario.usuarios
    ).execute(escenario.competicion.id.value)

    assert a.value in {r.user_id for r in tabla.rows}


async def _ryder_privada():
    """Una Ryder (privada al crearse) con una sesión de partidos."""
    from datetime import date as _date

    from src.modules.competition.domain.entities.round import Round
    from src.modules.competition.domain.value_objects.competition_id import CompetitionId
    from src.modules.competition.domain.value_objects.session_type import SessionType
    from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
        InMemoryUnitOfWork,
    )
    from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
    from src.shared.domain.value_objects.match_format import MatchFormat
    from tests.unit.modules.competition.application.use_cases.helpers import create_competition

    uow = InMemoryUnitOfWork()
    creada = await create_competition(uow, UserId(uuid4()))
    sesion = Round.create(
        competition_id=CompetitionId(creada.id),
        golf_course_id=GolfCourseId(uuid4()),
        round_date=_date(2026, 6, 1),
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )
    async with uow:
        await uow.rounds.add(sesion)
    return uow, creada, sesion


@pytest.mark.parametrize("cual", ["franja", "general", "scratch"])
async def test_de_fuera_de_una_ryder_privada_no_le_dice_ni_que_es_una_ryder(cual):
    """Revisor de la PR 2: antes, la puerta cortaba primero (403), no el tipo (400)."""
    uow, creada, sesion = await _ryder_privada()
    deps = {"uow": uow, "user_repository": MagicMock(), "eventos": _Eventos()}
    fuera = UserId(uuid4())
    llamadas = {
        "franja": lambda: ClasificacionDeLaFranjaUseCase(**deps).execute(
            sesion.id.value, quien=fuera
        ),
        "general": lambda: ClasificacionGeneralUseCase(**deps).execute(creada.id, quien=fuera),
        "scratch": lambda: ClasificacionScratchUseCase(**deps).execute(creada.id, fuera),
    }

    with pytest.raises(NoPuedeVerloError):
        await llamadas[cual]()


@pytest.mark.parametrize("cual", ["general", "scratch"])
async def test_dentro_de_una_ryder_si_le_dice_que_no_hay_clasificacion(cual):
    uow, creada, _ = await _ryder_privada()
    deps = {"uow": uow, "user_repository": MagicMock(), "eventos": _Eventos()}
    llamadas = {
        "general": lambda: ClasificacionGeneralUseCase(**deps).execute(
            creada.id, quien=UserId(uuid4()), es_admin=True
        ),
        "scratch": lambda: ClasificacionScratchUseCase(**deps).execute(
            creada.id, UserId(uuid4()), es_admin=True
        ),
    }

    with pytest.raises(PartidasError):
        await llamadas[cual]()


# --- Sin sesión (release social 3, tabla del 28 oct 2026: L2, L3) ------------------


def _publica(escenario) -> None:
    # Ya con partidas no se edita por la ficha: aquí basta con que lo sea
    escenario.competicion._visibility = Visibility.PUBLIC


@pytest.mark.parametrize("cual", ["franja", "general", "scratch"])
async def test_l2_sin_sesion_una_publica_se_ve_entera(cual):
    escenario, _, b, _ = await _dos_franjas()
    _publica(escenario)

    visitante = await _las_tres(escenario, _Eventos())[cual](None, visitante=True)
    dentro = await _las_tres(escenario, _Eventos())[cual](b)

    assert [r.user_id for r in visitante.rows] == [r.user_id for r in dentro.rows]
    assert visitante.me is None


@pytest.mark.parametrize("cual", ["franja", "general", "scratch"])
async def test_l3_sin_sesion_una_privada_no_aunque_haya_llave(cual):
    escenario, a, _, _ = await _dos_franjas()

    with pytest.raises(NoPuedeVerloError):
        await _las_tres(escenario, _Eventos(a))[cual](None, visitante=True)
