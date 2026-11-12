"""
`src.shared` no importa ningún módulo (hallazgo de la revisión de la fase 2; fase 5).

Quedaban cuatro excepciones en `.importlinter`:
- la autorización, que solo usaba el módulo de usuarios, se va a él;
- las rutas de países abrían la unidad de trabajo de competiciones para leer países, y usan el
  repositorio de países compartido;
- el servicio de tokens y el de correo heredaban de los puertos de los módulos (ABC); los
  puertos son ahora `Protocol` y se cumplen por su forma (lo comprueba mypy en la composition
  root).
Ahora el contrato se cumple sin excepciones (I1-I3).
"""

import importlib
from collections.abc import Iterator
from types import SimpleNamespace

import grimp
import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from src.config.dependencies import get_country_repository


def test_i1_shared_no_importa_ningun_modulo():
    """Given el grafo de importaciones, When se buscan importaciones de shared a un módulo, Then no hay ninguna."""
    grafo = grimp.build_graph("src", include_external_packages=False, cache_dir=None)
    directas = grafo.find_matching_direct_imports(
        import_expression="src.shared.** -> src.modules.**"
    )
    assert [(i["importer"], i["imported"]) for i in directas] == []


def test_i2_la_autorizacion_ya_no_vive_en_shared():
    """Given la ruta de antes, When se importa, Then falla: vive en el módulo de usuarios."""
    with pytest.raises(ImportError):
        importlib.import_module("src.shared.infrastructure.security.authorization")


def test_i2_sin_las_ayudas_que_nadie_usaba():
    """Given la autorización en usuarios, When se buscan las tres ayudas sin uso, Then ya no están."""
    autorizacion = importlib.import_module("src.modules.user.infrastructure.api.authorization")
    for muerta in (
        "can_modify_competition",
        "require_creator_or_admin",
        "require_player_in_competition",
    ):
        assert not hasattr(autorizacion, muerta), muerta
    for viva in (
        "is_admin",
        "is_creator_of",
        "is_player_in",
        "require_admin",
        "require_self_or_admin",
    ):
        assert hasattr(autorizacion, viva), viva


def _pais(codigo: str, en: str, es: str):
    return SimpleNamespace(code=SimpleNamespace(value=codigo), name_en=en, name_es=es)


class _PaisesFalsos:
    """El repositorio de países: España, con Francia y Portugal al lado."""

    async def find_all_active(self):
        return [_pais("ES", "Spain", "España"), _pais("FR", "France", "Francia")]

    async def find_by_code(self, code):
        return _pais("ES", "Spain", "España") if code.value == "ES" else None

    async def find_adjacent_countries(self, code):
        return [_pais("FR", "France", "Francia"), _pais("PT", "Portugal", "Portugal")]


@pytest.fixture
def pide() -> Iterator:
    """La app real con el repositorio de países sustituido."""
    app.dependency_overrides[get_country_repository] = _PaisesFalsos

    async def _pide(camino):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
            return await c.get("/api/v1/countries" + camino)

    try:
        yield _pide
    finally:
        app.dependency_overrides.pop(get_country_repository, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("camino", "codigo", "cuerpo"),
    [
        (
            "",
            200,
            [
                {"code": "ES", "name_en": "Spain", "name_es": "España"},
                {"code": "FR", "name_en": "France", "name_es": "Francia"},
            ],
        ),
        (
            "/es/adjacent",
            200,
            [
                {"code": "FR", "name_en": "France", "name_es": "Francia"},
                {"code": "PT", "name_en": "Portugal", "name_es": "Portugal"},
            ],
        ),
        ("/FR/adjacent", 404, {"detail": "País no encontrado: FR"}),
        ("/1A/adjacent", 400, {"detail": "Código de país inválido: 1A"}),
    ],
    ids=["todos", "adyacentes", "no-existe", "invalido"],
)
async def test_i3_las_rutas_de_paises_leen_del_repositorio_de_paises(pide, camino, codigo, cuerpo):
    """Given el repositorio de países, When se piden los países, Then la respuesta de siempre sale de él."""
    respuesta = await pide(camino)
    assert respuesta.status_code == codigo, respuesta.text
    assert respuesta.json() == cuerpo
