"""
La partida para anotar y las tarjetas de los suyos (#251, PR 5; pestañas 1 y 3).

| Caso                              | Resultado                                            |
|-----------------------------------|------------------------------------------------------|
| Recién generada                   | 18 hoyos vacíos, la hora de apertura, a quién marco |
| La hora de apertura               | Con el desfase del campo, como en la Ryder           |
| Tras anotar                       | Cada lado, su estado; totales solo de lo validado    |
| Quién puso el lado del marcador   | `marker_by`; sin anotar, null (QA 2, 12 oct)         |
| Y su nombre, aunque ya no esté    | `marker_by_name`                                     |
| El género de sus barras           | FEMALE de ella; sin género, null (12 oct)            |
| Una tarjeta entregada             | Su estado                                            |
| Medal                             | Sin levantar bola                                    |
| Una partida que no existe         | PartidaNotFoundError                                 |
"""

from dataclasses import replace
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.scoring_dto import SubmitHoleScoreBodyDTO
from src.modules.competition.application.exceptions import PartidaNotFoundError
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    AnotarHoyoDePartidaUseCase,
)
from src.modules.competition.application.use_cases.ver_anotacion_de_partida_use_case import (
    VerAnotacionDePartidaUseCase,
)
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    A_LAS_NUEVE_Y_CINCO,
    PRIMERA_SALIDA,
    _partida,
)

pytestmark = pytest.mark.asyncio


def _ver(escenario):
    return VerAnotacionDePartidaUseCase(
        uow=escenario.uow, zonas=escenario.zonas, user_repository=escenario.usuarios
    )


async def _anotar(escenario, partida, quien, hoyo, **body):
    body.setdefault("marked_player_id", str(partida.marcadores[quien].value))
    await AnotarHoyoDePartidaUseCase(
        uow=escenario.uow, zonas=escenario.zonas, reloj=lambda: A_LAS_NUEVE_Y_CINCO
    ).execute(partida.id.value, hoyo, SubmitHoleScoreBodyDTO(**body), quien)


async def test_a_new_group():
    escenario, partida = await _partida()
    a, b, _ = partida.user_ids

    vista = await _ver(escenario).execute(partida.id.value, a)

    assert (vista.number, vista.tee_time, vista.status) == (1, "09:00", "SCHEDULED")
    assert vista.scoring_opens_at == PRIMERA_SALIDA
    assert vista.i_mark_user_id == b.value
    assert vista.picked_up_allowed
    jugador = vista.players[0]
    assert len(jugador.holes) == 18
    assert jugador.holes[0].status == "PENDING"
    assert (jugador.totals.thru, jugador.totals.points) == (0, 0)
    assert jugador.card_status == "JUGANDO"
    assert jugador.name


async def test_the_opening_time_carries_the_course_offset():
    """
    Como `scoring_opens_at` de la Ryder: el cliente lee la hora de la cadena
    («la hora del campo»), así que en UTC anunciaba las 07:00 de una salida a
    las 09:00 en Madrid (pasada del front, FE #824).
    """
    escenario, partida = await _partida()
    a = partida.user_ids[0]

    vista = await _ver(escenario).execute(partida.id.value, a)

    assert vista.scoring_opens_at.isoformat() == "2030-10-11T09:00:00+02:00"


async def test_after_scoring_only_the_validated_count():
    escenario, partida = await _partida()
    a, b, c = partida.user_ids
    await _anotar(escenario, partida, a, 1, own_score=4, marked_score=5)
    await _anotar(escenario, partida, b, 1, own_score=5)
    await _anotar(escenario, partida, b, 2, own_score=4)

    vista = await _ver(escenario).execute(partida.id.value, c)

    suyo = next(p for p in vista.players if p.user_id == b.value)
    assert (suyo.holes[0].own_score, suyo.holes[0].marker_score, suyo.holes[0].status) == (
        5,
        5,
        "MATCH",
    )
    assert suyo.holes[1].status == "PENDING"
    assert suyo.totals.thru == 1
    assert suyo.totals.gross == 5
    assert suyo.marked_by_user_id == a.value
    # Su género, para «Retirada» / «No presentada» (pasada en el móvil, 12 oct)
    assert suyo.tee_gender == next(j for j in partida.jugadores if j.user_id == b).tee_gender.value
    assert vista.status == "IN_PROGRESS"
    # El número del lado del marcador lleva quién lo puso: tras cambiar el
    # círculo, el nuevo marcador ve que no es suyo (2.ª pasada del QA)
    assert suyo.holes[0].marker_by == a.value
    assert suyo.holes[1].marker_by is None
    # Y su nombre: puede no estar ya en la partida (12 oct 2026)
    nombre_de_a = next(p.name for p in vista.players if p.user_id == a.value)
    assert suyo.holes[0].marker_by_name == nombre_de_a
    assert suyo.holes[1].marker_by_name is None


async def test_who_scored_left_the_group_still_has_a_name():
    escenario, partida = await _partida()
    a, b, c = partida.user_ids
    await _anotar(escenario, partida, a, 1, own_score=4, marked_score=5)
    leida = await escenario.uow.partidas.find_by_id(partida.id)
    leida._jugadores = [j for j in leida._jugadores if j.user_id != a]
    leida._tarjetas.pop(a)
    leida._marcadores = {b: c, c: b}
    await escenario.uow.partidas.guardar([leida])

    vista = await _ver(escenario).execute(partida.id.value, c)

    suyo = next(p for p in vista.players if p.user_id == b.value)
    assert suyo.holes[0].marker_by == a.value
    assert suyo.holes[0].marker_by_name


async def test_a_delivered_card():
    escenario, partida = await _partida(n=2)
    a, b = partida.user_ids
    await _anotar(escenario, partida, a, 1, own_score=4)
    abierta = await escenario.uow.partidas.find_by_id(partida.id)
    abierta.entregar(a)
    await escenario.uow.partidas.guardar([abierta])

    vista = await _ver(escenario).execute(partida.id.value, b)

    assert {p.user_id: p.card_status for p in vista.players} == {
        a.value: "ENTREGADA",
        b.value: "JUGANDO",
    }


async def test_medal_does_not_allow_picking_up():
    escenario, partida = await _partida(tipo=TournamentType.MEDAL)

    vista = await _ver(escenario).execute(partida.id.value, partida.user_ids[0])

    assert (vista.tournament_type, vista.picked_up_allowed) == ("MEDAL", False)


async def test_a_group_that_does_not_exist():
    escenario, partida = await _partida()

    with pytest.raises(PartidaNotFoundError):
        await _ver(escenario).execute(uuid4(), partida.user_ids[0])


async def test_each_player_carries_the_gender_of_their_tee():
    from src.shared.domain.value_objects.gender import Gender

    escenario, partida = await _partida()
    a, b, c = partida.user_ids
    leida = await escenario.uow.partidas.find_by_id(partida.id)
    leida._jugadores = [
        replace(
            j,
            tee_gender=Gender.FEMALE
            if j.user_id == a
            else None
            if j.user_id == b
            else j.tee_gender,
        )
        for j in leida._jugadores
    ]
    await escenario.uow.partidas.guardar([leida])

    vista = await _ver(escenario).execute(partida.id.value, c)

    genero = {p.user_id: p.tee_gender for p in vista.players}
    assert genero[a.value] == "FEMALE"
    assert genero[b.value] is None
    assert genero[c.value] == "MALE"


async def test_each_player_says_if_they_played():
    # Para que el organizador vea «Retirar» y no «No presentado» (13 oct 2026):
    # a anota a b desde su pantalla; c no ha hecho nada
    escenario, partida = await _partida()
    a = partida.user_ids[0]
    b = partida.marcadores[a]

    await _anotar(escenario, partida, a, 1, marked_score=4)
    vista = await _ver(escenario).execute(partida.id.value, a)

    jugaron = {p.user_id for p in vista.players if p.played}
    assert jugaron == {a.value, b.value}


async def test_g2_the_group_says_the_golf_course_of_its_round():
    """
    GIVEN: Una partida de una franja que se juega en un campo
    WHEN: Se pide la vista de anotar
    THEN: Lleva el id de ese campo (para pedir el mapa de hoyos, BE #532)
    """
    escenario, partida = await _partida()
    a, _, _ = partida.user_ids
    franja = await escenario.uow.rounds.find_by_id(partida.round_id)

    vista = await _ver(escenario).execute(partida.id.value, a)

    assert vista.golf_course_id == franja.golf_course_id.value


class _NombresDeCampos:
    """Solo los nombres, como `find_names_by_ids` del repositorio de campos."""

    def __init__(self, nombres):
        self.nombres = nombres
        self.pedidos = []

    async def find_names_by_ids(self, ids):
        self.pedidos.append(list(ids))
        return {str(i): self.nombres[str(i)] for i in ids if str(i) in self.nombres}

    async def find_by_id(self, _course_id):
        return None


async def test_the_view_carries_the_course_name():
    """
    GIVEN: Una partida de stroke play y su campo
    WHEN: Se pide la anotación
    THEN: Lleva el nombre del campo, para enseñarlo bajo el título (BE #532, 16 oct)
    """
    escenario, partida = await _partida()
    franja = await escenario.uow.rounds.find_by_id(partida.round_id)
    campos = _NombresDeCampos({str(franja.golf_course_id): "Golf de Meis - Par 72"})

    vista = await VerAnotacionDePartidaUseCase(
        uow=escenario.uow,
        zonas=escenario.zonas,
        user_repository=escenario.usuarios,
        golf_courses=campos,
    ).execute(partida.id.value, partida.user_ids[0])

    assert vista.golf_course_name == "Golf de Meis - Par 72"
    assert campos.pedidos == [[franja.golf_course_id]]


async def test_the_course_name_is_null_if_the_course_is_not_found():
    """
    GIVEN: Un campo que ya no está (o sin repositorio de campos)
    WHEN: Se pide la anotación
    THEN: El nombre va a null, sin error
    """
    escenario, partida = await _partida()

    sin_campo = await VerAnotacionDePartidaUseCase(
        uow=escenario.uow,
        zonas=escenario.zonas,
        user_repository=escenario.usuarios,
        golf_courses=_NombresDeCampos({}),
    ).execute(partida.id.value, partida.user_ids[0])
    sin_repositorio = await _ver(escenario).execute(partida.id.value, partida.user_ids[0])

    assert sin_campo.golf_course_name is None
    assert sin_repositorio.golf_course_name is None


# Los metros de cada hoyo desde SU barra, para el recuadro del mapa (BE #532, 16 oct)


class _Salida:
    def __init__(self, metros):
        self.holes = [
            type("Hoyo", (), {"number": n, "meters": m})() for n, m in enumerate(metros, start=1)
        ]


class _CampoConSalidas(_NombresDeCampos):
    """Nombres y el campo entero, con sus salidas por (color, género)."""

    def __init__(self, nombres, salidas):
        super().__init__(nombres)
        self.salidas = salidas
        self.cargados = []

    async def find_by_id(self, course_id):
        self.cargados.append(course_id)
        salidas = self.salidas

        class _Campo:
            def tee_for(self, color, gender):
                return salidas.get((color, gender))

        return _Campo() if salidas is not None else None


def _con(escenario, campos):
    return VerAnotacionDePartidaUseCase(
        uow=escenario.uow,
        zonas=escenario.zonas,
        user_repository=escenario.usuarios,
        golf_courses=campos,
    )


async def test_b1_each_hole_carries_the_meters_of_the_players_own_tee():
    """
    GIVEN: Dos jugadores de la partida en barras distintas
    WHEN: Se pide la anotación
    THEN: Cada hoyo de cada uno lleva los metros de SU barra
    """
    from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
    from src.shared.domain.value_objects.gender import Gender

    escenario, partida = await _partida()
    a, b, _ = partida.user_ids
    leida = await escenario.uow.partidas.find_by_id(partida.id)
    leida._jugadores = [
        replace(j, tee_color=TeeColor.RED, tee_gender=Gender.FEMALE) if j.user_id == b else j
        for j in leida._jugadores
    ]
    await escenario.uow.partidas.guardar([leida])
    color_de_a = next(j for j in leida._jugadores if j.user_id == a)
    amarillas = _Salida([300 + n for n in range(18)])
    rojas = _Salida([250 + n for n in range(18)])
    campos = _CampoConSalidas(
        {},
        {
            (color_de_a.tee_color, color_de_a.tee_gender): amarillas,
            (TeeColor.RED, Gender.FEMALE): rojas,
        },
    )

    vista = await _con(escenario, campos).execute(partida.id.value, a)

    metros = {p.user_id: [h.meters for h in p.holes] for p in vista.players}
    assert metros[a.value][:3] == [300, 301, 302]
    assert metros[b.value][:3] == [250, 251, 252]
    assert metros[a.value][17] == 317


async def test_b2_a_hole_without_meters_on_the_tee_is_null():
    """
    GIVEN: Una barra a la que le faltan los metros del hoyo 2
    WHEN: Se pide la anotación
    THEN: Ese hoyo va con null; el resto, con los suyos
    """
    escenario, partida = await _partida()
    a = partida.user_ids[0]
    leida = await escenario.uow.partidas.find_by_id(partida.id)
    suyo = next(j for j in leida._jugadores if j.user_id == a)
    metros = [300] * 18
    metros[1] = None
    campos = _CampoConSalidas({}, {(suyo.tee_color, suyo.tee_gender): _Salida(metros)})

    vista = await _con(escenario, campos).execute(partida.id.value, a)

    suyos = next(p for p in vista.players if p.user_id == a.value).holes
    assert [h.meters for h in suyos[:3]] == [300, None, 300]


async def test_b3_a_tee_no_longer_on_the_course_gives_null_everywhere():
    """
    GIVEN: Un campo que ya no tiene la barra de los jugadores (o sin tarjeta)
    WHEN: Se pide la anotación
    THEN: Todos sus hoyos, con null
    """
    escenario, partida = await _partida()
    sin_barra = await _con(escenario, _CampoConSalidas({}, {})).execute(
        partida.id.value, partida.user_ids[0]
    )
    leida = await escenario.uow.partidas.find_by_id(partida.id)
    suyo = leida._jugadores[0]
    sin_tarjeta = await _con(
        escenario, _CampoConSalidas({}, {(suyo.tee_color, suyo.tee_gender): _Salida([])})
    ).execute(partida.id.value, partida.user_ids[0])

    for vista in (sin_barra, sin_tarjeta):
        assert all(h.meters is None for p in vista.players for h in p.holes)


async def test_b4_without_the_course_or_its_repository_meters_are_null():
    """
    GIVEN: Un campo que no se encuentra, o sin repositorio de campos
    WHEN: Se pide la anotación
    THEN: Los metros van a null, sin error
    """
    escenario, partida = await _partida()

    sin_campo = await _con(escenario, _CampoConSalidas({}, None)).execute(
        partida.id.value, partida.user_ids[0]
    )
    sin_repositorio = await _ver(escenario).execute(partida.id.value, partida.user_ids[0])

    for vista in (sin_campo, sin_repositorio):
        assert all(h.meters is None for p in vista.players for h in p.holes)


async def test_b6_the_course_is_loaded_once_per_view():
    """
    GIVEN: Una partida de tres jugadores
    WHEN: Se pide la anotación
    THEN: El campo se carga una sola vez, no una por jugador
    """
    escenario, partida = await _partida()
    campos = _CampoConSalidas({}, {})

    await _con(escenario, campos).execute(partida.id.value, partida.user_ids[0])

    assert len(campos.cargados) == 1
