"""
Lo jugado de una privada, por la API (tabla del 27 oct 2026).

La regla la cubren los tests de la puerta; aquí, que cada ruta le pregunta lo
suyo y que su «no» es un 403 con su código antes de leer nada más.
"""

import uuid
from datetime import date, timedelta
from typing import ClassVar

import pytest
from httpx import AsyncClient

from src.modules.competition.application.services.lo_jugado_de_una_privada import (
    NoPuedeVerloError,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from tests.conftest import create_authenticated_user, create_competition, set_auth_cookies

pytestmark = pytest.mark.asyncio


class _Puerta:
    """Apunta qué le preguntan; con `cierra`, dice que no."""

    llamadas: ClassVar[list] = []
    cierra: ClassVar[bool] = True

    def _apunta(self, metodo, ident, quien, es_admin):
        type(self).llamadas.append((metodo, ident, str(quien.value), es_admin))
        if type(self).cierra:
            raise NoPuedeVerloError

    async def exigir_la_clasificacion(self, competition_id, quien, *, es_admin=False):
        self._apunta("clasificacion", competition_id, quien, es_admin)
        return LO_QUE_VE

    async def exigir_la_clasificacion_de_la_ronda(self, round_id, quien, *, es_admin=False):
        self._apunta("ronda", round_id, quien, es_admin)

    async def exigir_el_partido(self, match_id, quien, *, es_admin=False):
        self._apunta("partido", match_id, quien, es_admin)

    async def exigir_la_partida(self, partida_id, quien, *, es_admin=False):
        self._apunta("partida", partida_id, quien, es_admin)


# Lo que la puerta dice que ve: la clasificación de la Ryder se lo pasa a su caso de uso
LO_QUE_VE = object()
ID = uuid.UUID("7a1e0c3e-27a0-4c1d-9f00-000000000027")
RUTAS = [
    (f"/api/v1/competitions/{ID}/leaderboard", "clasificacion", CompetitionId(ID)),
    (f"/api/v1/competitions/{ID}/standings", "clasificacion", CompetitionId(ID)),
    (f"/api/v1/competitions/{ID}/standings/scratch", "clasificacion", CompetitionId(ID)),
    (f"/api/v1/competitions/rounds/{ID}/standings", "ronda", RoundId(ID)),
    (f"/api/v1/competitions/matches/{ID}", "partido", MatchId(ID)),
    (f"/api/v1/competitions/matches/{ID}/scoring-view", "partido", MatchId(ID)),
    (f"/api/v1/competitions/groups/{ID}/scoring-view", "partida", PartidaId(ID)),
]


@pytest.fixture
async def con_la_puerta(client: AsyncClient):
    from main import app
    from src.config.dependencies import get_puerta_de_lo_jugado

    yo = await create_authenticated_user(
        client, f"lj_{uuid.uuid4().hex[:8]}@test.com", "P@ssw0rd123!", "Mira", "Fuera"
    )
    set_auth_cookies(client, yo["cookies"])
    _Puerta.llamadas = []
    app.dependency_overrides[get_puerta_de_lo_jugado] = _Puerta
    try:
        yield yo
    finally:
        app.dependency_overrides.pop(get_puerta_de_lo_jugado, None)
        _Puerta.cierra = True


@pytest.mark.parametrize(("ruta", "metodo", "ident"), RUTAS)
async def test_6_cerrada_es_un_403_con_su_codigo(client, con_la_puerta, ruta, metodo, ident):
    _Puerta.cierra = True

    r = await client.get(ruta)

    assert r.status_code == 403, r.text
    assert r.json()["error_code"] == "PRIVATE_COMPETITION"
    assert _Puerta.llamadas == [(metodo, ident, con_la_puerta["user"]["id"], False)]


@pytest.mark.parametrize(("ruta", "metodo", "ident"), RUTAS)
async def test_abierta_sigue_a_su_caso_de_uso(client, con_la_puerta, ruta, metodo, ident):
    """Con la puerta abierta llega a su caso de uso, que dice lo suyo del id inventado."""
    _Puerta.cierra = False

    r = await client.get(ruta)

    assert r.status_code != 403, r.text
    assert [m for m, *_ in _Puerta.llamadas] == [metodo]


# --- De verdad, con la puerta real --------------------------------------------------


async def _jugador(client: AsyncClient, nombre: str) -> dict:
    return await create_authenticated_user(
        client,
        f"ljr_{nombre.lower()}_{uuid.uuid4().hex[:6]}@test.com",
        "P@ssw0rd123!",
        nombre,
        "Real",
    )


def _datos(visibilidad: str, stroke_play: bool) -> dict:
    start = date.today() + timedelta(days=30)
    datos = {
        "name": f"LJ {uuid.uuid4().hex[:8]}",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=1)).isoformat(),
        "main_country": "ES",
        "play_mode": "HANDICAP",
        "max_players": 12,
        "visibility": visibilidad,
    }
    if stroke_play:
        return {
            **datos,
            "tournament_type": "STABLEFORD",
            "stroke_play": {"category_limits": [36.0]},
        }
    return {**datos, "team_assignment": "MANUAL"}


async def _mira(client: AsyncClient, quien: dict, ruta: str) -> int:
    set_auth_cookies(client, quien["cookies"])
    return (await client.get(ruta)).status_code


async def test_6_la_clasificacion_ryder_de_una_privada_cerrada_a_quien_no_esta(client):
    creador, curioso = await _jugador(client, "Org"), await _jugador(client, "Curioso")
    privada = await create_competition(client, creador["cookies"], _datos("PRIVATE", False))
    publica = await create_competition(client, creador["cookies"], _datos("PUBLIC", False))

    assert await _mira(client, curioso, f"/api/v1/competitions/{privada['id']}/leaderboard") == 403
    assert await _mira(client, creador, f"/api/v1/competitions/{privada['id']}/leaderboard") == 200
    assert await _mira(client, curioso, f"/api/v1/competitions/{publica['id']}/leaderboard") == 200


async def test_6_las_clasificaciones_de_stroke_play_de_una_privada_tambien(client):
    creador, curioso = await _jugador(client, "Orga"), await _jugador(client, "Curiosa")
    # Un Stableford exige el hándicap de quien lo crea: juega en él
    set_auth_cookies(client, creador["cookies"])
    r = await client.post(
        "/api/v1/handicaps/update", json={"user_id": creador["user"]["id"], "manual_handicap": 15.0}
    )
    assert r.status_code == 200, r.text
    privada = await create_competition(client, creador["cookies"], _datos("PRIVATE", True))
    publica = await create_competition(client, creador["cookies"], _datos("PUBLIC", True))

    for ruta in ("standings", "standings/scratch"):
        assert await _mira(client, curioso, f"/api/v1/competitions/{privada['id']}/{ruta}") == 403
        assert await _mira(client, creador, f"/api/v1/competitions/{privada['id']}/{ruta}") == 200
        assert await _mira(client, curioso, f"/api/v1/competitions/{publica['id']}/{ruta}") == 200


# --- De extremo a extremo, con partidas generadas (revisor) --------------------------


async def _con_dos_partidas(client: AsyncClient):
    """Una privada de stroke play: el organizador y 7 más, en dos partidas."""
    from tests.integration.api.v1.test_tee_groups_endpoints import _generar, _stableford

    organizador, competicion, franja, otros = await _stableford(client, jugadores=7)
    generadas = await _generar(client, organizador, franja)
    assert generadas.status_code == 200, generadas.text
    grupos = generadas.json()["groups"]
    assert len(grupos) == 2
    return organizador, competicion, franja, otros, grupos


async def _escribe_la_llave(yo: dict, amigo: dict, competicion: dict) -> None:
    from datetime import datetime

    from main import app
    from src.config.dependencies import get_db_session
    from src.modules.social.domain.entities.activity_event import ActivityEvent
    from src.modules.social.domain.entities.friendship import Friendship
    from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
    from src.modules.social.domain.value_objects.friendship_id import FriendshipId
    from src.modules.social.infrastructure.persistence.sqlalchemy.activity_event_repository import (
        SQLAlchemyActivityEventRepository,
    )
    from src.modules.social.infrastructure.persistence.sqlalchemy.friendship_repository import (
        SQLAlchemyFriendshipRepository,
    )
    from src.modules.user.domain.value_objects.user_id import UserId

    amistad = Friendship.create(
        id=FriendshipId(uuid.uuid4()),
        requester_id=UserId(yo["user"]["id"]),
        addressee_id=UserId(amigo["user"]["id"]),
    )
    amistad.accept()
    cuando = datetime(2026, 10, 20, 12, 0)
    birdie = ActivityEvent.create(
        user_id=UserId(amigo["user"]["id"]),
        type=ActivityEventType.BIRDIE,
        occurred_at=cuando,
        source_match_id=f"grupo-{uuid.uuid4().hex[:6]}",
        published_at=cuando,
        payload={"competition_id": competicion["id"], "from_tournament": True},
    )
    async for session in app.dependency_overrides[get_db_session]():
        try:
            await SQLAlchemyFriendshipRepository(session).add(amistad)
            await SQLAlchemyActivityEventRepository(session).add_many([birdie])
            await session.commit()
            return
        finally:
            await session.close()
    raise AssertionError("sin sesión de BD")


def _grupo_de(grupos: list, jugador: dict) -> str:
    (grupo,) = [
        g["id"] for g in grupos if jugador["user"]["id"] in {p["user_id"] for p in g["players"]}
    ]
    return grupo


async def test_2_5_el_aprobado_lo_ve_todo_y_al_retirarse_ya_no(client):
    _, competicion, _, otros, grupos = await _con_dos_partidas(client)
    jugador = otros[0]
    ajeno = next(g["id"] for g in grupos if g["id"] != _grupo_de(grupos, jugador))
    standings = f"/api/v1/competitions/{competicion['id']}/standings"
    otra_partida = f"/api/v1/competitions/groups/{ajeno}/scoring-view"

    assert await _mira(client, jugador, standings) == 200
    assert await _mira(client, jugador, otra_partida) == 200

    set_auth_cookies(client, jugador["cookies"])
    inscritos = (
        await client.get(f"/api/v1/competitions/{competicion['id']}/enrollments?status=APPROVED")
    ).json()
    (suya,) = [i for i in inscritos if i["user_id"] == jugador["user"]["id"]]
    retirada = await client.post(f"/api/v1/enrollments/{suya['id']}/withdraw", json={})
    assert retirada.status_code == 200, retirada.text

    assert await _mira(client, jugador, standings) == 403
    assert await _mira(client, jugador, otra_partida) == 403


async def test_7_con_la_llave_la_clasificacion_y_solo_la_partida_de_su_amigo(client):
    _, competicion, franja, otros, grupos = await _con_dos_partidas(client)
    amigo = otros[1]
    suya = _grupo_de(grupos, amigo)
    otra = next(g["id"] for g in grupos if g["id"] != suya)
    yo = await _jugador(client, "Llave")
    base = f"/api/v1/competitions/{competicion['id']}"

    # Sin la llave, nada
    assert await _mira(client, yo, f"{base}/standings") == 403
    assert await _mira(client, yo, f"/api/v1/competitions/groups/{suya}/scoring-view") == 403

    await _escribe_la_llave(yo, amigo, competicion)

    assert await _mira(client, yo, f"{base}/standings") == 200
    assert await _mira(client, yo, f"{base}/standings/scratch") == 200
    assert await _mira(client, yo, f"/api/v1/competitions/rounds/{franja}/standings") == 200
    assert await _mira(client, yo, f"/api/v1/competitions/groups/{suya}/scoring-view") == 200
    assert await _mira(client, yo, f"/api/v1/competitions/groups/{otra}/scoring-view") == 403
    set_auth_cookies(client, yo["cookies"])
    vista = (await client.get(f"/api/v1/competitions/rounds/{franja}/groups")).json()
    assert [g["id"] for g in vista["groups"]] == [suya]
    # La lista de inscritos sigue cerrada: solo la clasificación y su partida
    assert (await client.get(f"{base}/enrollments")).json() == []


async def test_7_la_clasificacion_ryder_filtra_con_lo_que_ve(client, con_la_puerta):
    """Con la llave, la Ryder: el marcador y solo el partido de su amigo (27 oct)."""
    from main import app
    from src.config.dependencies import get_get_leaderboard_use_case

    llamadas = []

    class _Clasificacion:
        async def execute(self, *args):
            llamadas.append(args)
            raise _BastaError

    _Puerta.cierra = False
    app.dependency_overrides[get_get_leaderboard_use_case] = _Clasificacion
    try:
        r = await client.get(f"/api/v1/competitions/{ID}/leaderboard")
    finally:
        app.dependency_overrides.pop(get_get_leaderboard_use_case, None)

    assert r.status_code == 500
    assert llamadas == [(str(ID), LO_QUE_VE)]


class _BastaError(Exception):
    pass
