"""
Las rutas de competición piden la vista a su caso de uso, no al repositorio (fase 5, PR 3a).

Tras una transición, un alta o una edición, la ruta volvía a leer la competición con
`uow.competitions.find_by_id` y la pasaba por el mapper. Ahora lo hace
`VistaDeCompeticionUseCase`. Lo único que cambia, a propósito: si la competición
desaparece entre la escritura y la lectura (una carrera), una transición daba 500
porque el mapper recibía None, y ahora da 404 como `update` (R1, R2). El alta sigue
con su 500 (R3). Y las rutas de estado no tocan la unidad de trabajo (G1).
"""

import ast
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from src.config import dependencies as d
from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.application.use_cases.vista_de_competicion_use_case import (
    VistaDeCompeticionUseCase,
)

COMPETICION = UUID("5b0c6a2e-1d3f-4e8a-9b7c-2f4d6e8a0b1c")
BASE = "/api/v1/competitions"
RAIZ = Path(__file__).resolve().parents[7]
RUTAS_DE_ESTADO = RAIZ / "src/modules/competition/infrastructure/api/v1/competition_state_routes.py"

CUERPO_DE_ALTA = {
    "name": "Ryder de prueba",
    "start_date": "2027-06-01",
    "end_date": "2027-06-02",
    "main_country": "ES",
    "play_mode": "SCRATCH",
    "max_players": 24,
    "team_assignment": "MANUAL",
}


class _Usuario:
    """Lo que las rutas leen de quien llama."""

    id = "3f2b8c1e-9d4a-4e7b-8a2f-1c5d6e7f8a9b"
    is_admin = True
    email = "admin@t.com"
    email_verified = True


class _CasoDeUsoQueEscribe:
    """Transición, alta o edición falsa: escribe sin fallar."""

    async def execute(self, *args, **kwargs):
        """Lo que devuelve el alta: el id de la nueva."""
        return SimpleNamespace(id=COMPETICION)


def _vista_sin_competicion() -> VistaDeCompeticionUseCase:
    """La vista de verdad con una BD donde la competición ya no está."""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.competitions.find_by_id = AsyncMock(return_value=None)
    user_uow = MagicMock()
    user_uow.__aenter__ = AsyncMock(return_value=user_uow)
    user_uow.__aexit__ = AsyncMock(return_value=False)
    return VistaDeCompeticionUseCase(uow, user_uow)


@pytest.fixture
def pide() -> Iterator:
    """Llama a la app real con el usuario, la escritura y la vista sustituidos."""
    tocadas = [d.get_current_user, d.get_vista_de_competicion_use_case]

    async def _pide(metodo, camino, dependencia, cuerpo=None):
        app.dependency_overrides[d.get_current_user] = _Usuario
        app.dependency_overrides[d.get_vista_de_competicion_use_case] = _vista_sin_competicion
        app.dependency_overrides[dependencia] = _CasoDeUsoQueEscribe
        tocadas.append(dependencia)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as cliente:
            return await cliente.request(
                metodo, BASE + camino, json=cuerpo, headers={"X-CSRF-Token": "x"}
            )

    try:
        yield _pide
    finally:
        for dependencia in tocadas:
            app.dependency_overrides.pop(dependencia, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("metodo", "camino", "dependencia"),
    [
        ("POST", "activate", d.get_activate_competition_use_case),
        ("POST", "close-enrollments", d.get_close_enrollments_use_case),
        ("POST", "start", d.get_start_competition_use_case),
        ("POST", "complete", d.get_complete_competition_use_case),
        ("PUT", "revert-status", d.get_revert_competition_status_use_case),
        ("PUT", "revert-to-in-progress", d.get_revert_competition_to_in_progress_use_case),
        ("POST", "reopen-enrollments", d.get_reopen_enrollments_use_case),
        ("POST", "cancel", d.get_cancel_competition_use_case),
    ],
)
async def test_r1_transicion_si_la_competicion_desaparece_da_404(pide, metodo, camino, dependencia):
    """Given la competición borrada tras la transición, When se pide la vista, Then 404."""
    respuesta = await pide(metodo, f"/{COMPETICION}/{camino}", dependencia)

    assert respuesta.status_code == 404, respuesta.text
    assert respuesta.json() == {"detail": f"No existe competición con ID {COMPETICION}"}


@pytest.mark.asyncio
async def test_r2_edicion_si_la_competicion_desaparece_da_404(pide):
    """Given la competición borrada tras editarla, When se pide la vista, Then 404."""
    respuesta = await pide(
        "PUT", f"/{COMPETICION}", d.get_update_competition_use_case, {"name": "Otro nombre"}
    )

    assert respuesta.status_code == 404, respuesta.text
    assert respuesta.json() == {"detail": f"No existe competición con ID {COMPETICION}"}


@pytest.mark.asyncio
async def test_r3_alta_si_la_competicion_desaparece_sigue_dando_500(pide):
    """Given la competición recién creada que no se encuentra, When se pide la vista, Then 500."""
    respuesta = await pide("POST", "", d.get_create_competition_use_case, CUERPO_DE_ALTA)

    assert respuesta.status_code == 500, respuesta.text
    assert respuesta.json() == {"detail": "Competition created but not found"}


def test_g1_las_rutas_de_estado_no_tocan_la_unidad_de_trabajo():
    """
    Given las rutas de estado, When se recorren, Then ninguna recibe `uow` ni `user_uow`
    ni lee de un repositorio: la vista se la pide a su caso de uso.
    """
    arbol = ast.parse(RUTAS_DE_ESTADO.read_text())
    usos = sorted(
        {
            f"{n.lineno}: {ast.unparse(n)}"
            for n in ast.walk(arbol)
            if (isinstance(n, ast.arg) and n.arg in {"uow", "user_uow"})
            or (isinstance(n, ast.Name) and n.id in {"uow", "user_uow"})
            or (isinstance(n, ast.Name) and n.id in {"get_competition_uow", "get_uow"})
        }
    )
    assert usos == []


class _VistaEspia:
    """Apunta con qué se le pide la vista y responde que no está (así la ruta acaba en 404)."""

    def __init__(self) -> None:
        self.llamadas: list[tuple] = []

    async def de(self, competition_id, quien, *, es_admin=False):
        """Apunta la llamada."""
        self.llamadas.append(("de", competition_id.value, quien.value, es_admin, None))
        raise CompetitionNotFoundError("x")

    async def ficha(self, competition_id, quien, *, es_admin=False, email=None):
        """Apunta la llamada."""
        self.llamadas.append(("ficha", competition_id.value, quien.value, es_admin, email))
        raise CompetitionNotFoundError("x")


class _NoEstorba:
    """GetCompetitionUseCase falso: la competición existe."""

    async def execute(self, *args, **kwargs):
        """Nada que hacer."""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("metodo", "camino", "dependencia", "cuerpo", "esperada"),
    [
        ("POST", f"/{COMPETICION}/activate", d.get_activate_competition_use_case, None, "de"),
        (
            "PUT",
            f"/{COMPETICION}/revert-status",
            d.get_revert_competition_status_use_case,
            None,
            "de",
        ),
        ("POST", f"/{COMPETICION}/cancel", d.get_cancel_competition_use_case, None, "de"),
        (
            "PUT",
            f"/{COMPETICION}",
            d.get_update_competition_use_case,
            {"name": "Otro nombre"},
            "de",
        ),
        ("GET", f"/{COMPETICION}", d.get_get_competition_use_case, None, "ficha"),
    ],
)
async def test_r4_la_ruta_pasa_quien_mira_y_si_es_admin(
    metodo, camino, dependencia, cuerpo, esperada
):
    """Given un admin que escribe o mira, When la ruta pide la vista, Then le pasa quién y que es admin."""
    espia = _VistaEspia()
    app.dependency_overrides[d.get_current_user] = _Usuario
    app.dependency_overrides[d.get_vista_de_competicion_use_case] = lambda: espia
    app.dependency_overrides[dependencia] = (
        _NoEstorba if dependencia is d.get_get_competition_use_case else _CasoDeUsoQueEscribe
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as cliente:
            respuesta = await cliente.request(
                metodo, BASE + camino, json=cuerpo, headers={"X-CSRF-Token": "x"}
            )
    finally:
        for dep in (d.get_current_user, d.get_vista_de_competicion_use_case, dependencia):
            app.dependency_overrides.pop(dep, None)

    assert respuesta.status_code == 404, respuesta.text
    correo = _Usuario.email if esperada == "ficha" else None
    assert espia.llamadas == [(esperada, COMPETICION, UUID(_Usuario.id), True, correo)]


@pytest.mark.asyncio
async def test_r4_el_alta_pide_la_vista_de_quien_la_crea_sin_ser_admin():
    """Given un admin que crea, When la ruta pide la vista, Then la pide como creador, no como admin (como antes)."""
    espia = _VistaEspia()
    app.dependency_overrides[d.get_current_user] = _Usuario
    app.dependency_overrides[d.get_vista_de_competicion_use_case] = lambda: espia
    app.dependency_overrides[d.get_create_competition_use_case] = _CasoDeUsoQueEscribe
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as cliente:
            respuesta = await cliente.post(BASE, json=CUERPO_DE_ALTA, headers={"X-CSRF-Token": "x"})
    finally:
        for dep in (
            d.get_current_user,
            d.get_vista_de_competicion_use_case,
            d.get_create_competition_use_case,
        ):
            app.dependency_overrides.pop(dep, None)

    assert respuesta.status_code == 500, respuesta.text
    assert espia.llamadas == [("de", COMPETICION, UUID(_Usuario.id), False, None)]


RUTAS_CRUD = RAIZ / "src/modules/competition/infrastructure/api/v1/competition_crud_routes.py"


class _ListadoEspia:
    """ListCompetitionsUseCase falso: apunta qué método se llama y con qué."""

    def __init__(self) -> None:
        self.llamadas: list[tuple] = []

    async def listar(self, estados, **kwargs):
        """Apunta la llamada."""
        self.llamadas.append(("listar", estados, kwargs))
        return ["c"]

    async def mis_competiciones(self, quien, estados, **kwargs):
        """Apunta la llamada."""
        self.llamadas.append(("mis_competiciones", quien.value, estados, kwargs))
        return ["c"]

    async def las_de_los_demas(self, quien, estados, **kwargs):
        """Apunta la llamada."""
        self.llamadas.append(("las_de_los_demas", quien.value, estados, kwargs))
        return ["c"]


class _VistaDeListado:
    """Vista falsa del listado: apunta con qué se le pide y no devuelve ninguna."""

    def __init__(self) -> None:
        self.llamadas: list[tuple] = []

    async def de_varias(self, competiciones, quien, *, es_admin=False):
        """Apunta la llamada."""
        self.llamadas.append((competiciones, quien.value, es_admin))
        return []


QUIEN = UUID(_Usuario.id)
FILTROS = {"search_name": "copa", "search_creator": "ana"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("consulta", "esperada"),
    [
        (
            "?my_competitions=true&status=ACTIVE&search_name=copa&search_creator=ana",
            ("mis_competiciones", QUIEN, ["ACTIVE"], {**FILTROS, "viewer_email": _Usuario.email}),
        ),
        (
            "?my_competitions=false&status=ACTIVE&creator_id=undefined&search_name=copa&search_creator=ana",
            (
                "las_de_los_demas",
                QUIEN,
                ["ACTIVE"],
                {
                    "creator_id": None,
                    **FILTROS,
                    "is_admin": True,
                    "viewer_email": _Usuario.email,
                },
            ),
        ),
        (
            "?status=ACTIVE&status=DRAFT&creator_id=abc&search_name=copa&search_creator=ana",
            (
                "listar",
                ["ACTIVE", "DRAFT"],
                {
                    "creator_id": "abc",
                    **FILTROS,
                    "viewer_id": str(QUIEN),
                    "is_admin": True,
                    "viewer_email": _Usuario.email,
                },
            ),
        ),
    ],
    ids=["mias", "de-los-demas", "todas"],
)
async def test_l9_el_listado_llama_al_metodo_que_toca(consulta, esperada):
    """Given un filtro del listado, When se pide, Then la ruta llama al método que toca con quien mira."""
    listado, vista = _ListadoEspia(), _VistaDeListado()
    app.dependency_overrides[d.get_current_user] = _Usuario
    app.dependency_overrides[d.get_list_competitions_use_case] = lambda: listado
    app.dependency_overrides[d.get_vista_de_competicion_use_case] = lambda: vista
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as cliente:
            respuesta = await cliente.get(BASE + consulta)
    finally:
        for dep in (
            d.get_current_user,
            d.get_list_competitions_use_case,
            d.get_vista_de_competicion_use_case,
        ):
            app.dependency_overrides.pop(dep, None)

    assert respuesta.status_code == 200, respuesta.text
    assert listado.llamadas == [esperada]
    assert vista.llamadas == [(["c"], QUIEN, True)]


def test_g2_las_rutas_crud_no_tocan_la_unidad_de_trabajo():
    """Given las rutas CRUD, When se recorren, Then ninguna recibe ni usa la unidad de trabajo ni el mapper."""
    arbol = ast.parse(RUTAS_CRUD.read_text())
    prohibidos = {"uow", "user_uow", "get_competition_uow", "get_uow", "CompetitionDTOMapper"}
    usos = sorted(
        {
            f"{n.lineno}: {ast.unparse(n)}"
            for n in ast.walk(arbol)
            if (isinstance(n, ast.arg) and n.arg in prohibidos)
            or (isinstance(n, ast.Name) and n.id in prohibidos)
            or (isinstance(n, ast.alias) and n.name in prohibidos)
        }
    )
    assert usos == []
