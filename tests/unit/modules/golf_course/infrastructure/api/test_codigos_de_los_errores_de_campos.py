"""
Las rutas de campos responden el mismo código que antes, ahora por el tipo del error.

Hasta ahora la ruta miraba el texto del `ValueError` («not found» → 404,
«permission» → 403, el resto → 400). Los casos de uso lanzan ya errores con tipo
y la ruta decide por el tipo; para el cliente no cambia nada: ni el código ni el
`detail` (G1-G9). Y la ruta ya no lee el texto para elegir el código (G11).
"""

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from src.config.dependencies import (
    get_approve_golf_course_use_case,
    get_approve_update_golf_course_use_case,
    get_create_direct_golf_course_use_case,
    get_current_user,
    get_get_golf_course_by_id_use_case,
    get_reject_golf_course_use_case,
    get_reject_update_golf_course_use_case,
    get_request_golf_course_use_case,
    get_update_golf_course_use_case,
)
from src.modules.golf_course.application.exceptions import (
    CountryNotFoundError,
    GolfCourseEditForbiddenError,
    GolfCourseMissingError,
)

pytestmark = pytest.mark.asyncio

CAMPO = "6f1d2c3b-4a5e-4f60-8a7b-9c0d1e2f3a4b"
BASE = "/api/v1/golf-courses"
RUTAS = Path("src/modules/golf_course/infrastructure/api/v1/golf_course_routes.py")

CUERPO_DE_CAMPO = {
    "name": "Real Club de Golf El Prat",
    "country_code": "ES",
    "course_type": "STANDARD_18",
    "tees": [
        {
            "identifier": "Blanco",
            "color": "WHITE",
            "tee_gender": "MALE",
            "course_rating": 72.5,
            "slope_rating": 135,
            "par": 72,
        },
        {
            "identifier": "Amarillo",
            "color": "YELLOW",
            "tee_gender": "MALE",
            "course_rating": 70.2,
            "slope_rating": 128,
            "par": 72,
        },
    ],
    "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
}

NO_ESTA = GolfCourseMissingError(f"Golf course not found: {CAMPO}")
PROPUESTA_NO_ESTA = GolfCourseMissingError(f"Golf course clone with ID {CAMPO} not found")
ORIGINAL_NO_ESTA = GolfCourseMissingError(f"Original golf course {CAMPO} not found")
SIN_PERMISO = GolfCourseEditForbiddenError(
    f"User x does not have permission to edit golf course {CAMPO}"
)
SIN_PAIS = CountryNotFoundError("Country with code 'ZZ' not found")
NO_ES_PROPUESTA = ValueError(
    f"Golf course {CAMPO} is not a clone/update proposal. "
    "It does not have an original_golf_course_id."
)


class _Admin:
    """Lo que las rutas leen del usuario actual: su id y si es admin."""

    id = "3f2b8c1e-9d4a-4e7b-8a2f-1c5d6e7f8a9b"
    is_admin = True


class _CasoDeUsoQueFalla:
    """Caso de uso falso que lanza el error que se le da."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def execute(self, *args, **kwargs):
        """Lanza el error, sea cual sea la petición."""
        raise self._error


# (dependencia, método, ruta, cuerpo)
GET = (get_get_golf_course_by_id_use_case, "GET", f"/{CAMPO}", None)
UPDATE = (get_update_golf_course_use_case, "PUT", f"/{CAMPO}", CUERPO_DE_CAMPO)
APPROVE = (get_approve_golf_course_use_case, "PUT", f"/admin/{CAMPO}/approve", None)
REJECT = (
    get_reject_golf_course_use_case,
    "PUT",
    f"/admin/{CAMPO}/reject?reason=Datos%20incompletos",
    None,
)
APPROVE_UPDATE = (
    get_approve_update_golf_course_use_case,
    "PUT",
    f"/admin/{CAMPO}/approve-update",
    None,
)
REJECT_UPDATE = (
    get_reject_update_golf_course_use_case,
    "PUT",
    f"/admin/{CAMPO}/reject-update",
    None,
)
REQUEST = (get_request_golf_course_use_case, "POST", "/request", CUERPO_DE_CAMPO)
CREATE = (get_create_direct_golf_course_use_case, "POST", "/admin", CUERPO_DE_CAMPO)


@pytest.fixture
def pide() -> Iterator:
    """Llama a la app real con el usuario y el caso de uso sustituidos."""
    tocadas = []

    async def _pide(ruta, error):
        dependencia, metodo, camino, cuerpo = ruta
        app.dependency_overrides[get_current_user] = _Admin
        app.dependency_overrides[dependencia] = lambda: _CasoDeUsoQueFalla(error)
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
        app.dependency_overrides.pop(get_current_user, None)
        for dependencia in tocadas:
            app.dependency_overrides.pop(dependencia, None)


@pytest.mark.parametrize(
    ("caso", "ruta", "error", "codigo"),
    [
        ("G1 ver un campo que no existe", GET, NO_ESTA, 404),
        ("G2 editar un campo que no existe", UPDATE, NO_ESTA, 404),
        ("G3 editar sin ser creador ni admin", UPDATE, SIN_PERMISO, 403),
        ("G4 editar con un país que no existe", UPDATE, SIN_PAIS, 404),
        ("G5 editar con otro ValueError", UPDATE, ValueError("Cannot edit a REJECTED"), 400),
        ("G6 aprobar un campo que no existe", APPROVE, NO_ESTA, 404),
        ("G6 rechazar un campo que no existe", REJECT, NO_ESTA, 404),
        ("G7 aprobar una propuesta que no existe", APPROVE_UPDATE, PROPUESTA_NO_ESTA, 404),
        ("G7 rechazar una propuesta que no existe", REJECT_UPDATE, PROPUESTA_NO_ESTA, 404),
        ("G7 aprobar una propuesta sin original", APPROVE_UPDATE, ORIGINAL_NO_ESTA, 404),
        ("G7 rechazar una propuesta sin original", REJECT_UPDATE, ORIGINAL_NO_ESTA, 404),
        ("G8 aprobar algo que no es una propuesta", APPROVE_UPDATE, NO_ES_PROPUESTA, 400),
        ("G8 rechazar algo que no es una propuesta", REJECT_UPDATE, NO_ES_PROPUESTA, 400),
        ("G9 solicitar un campo con un país que no existe", REQUEST, SIN_PAIS, 400),
        ("G9 crear un campo (admin) con un país que no existe", CREATE, SIN_PAIS, 400),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
async def test_el_codigo_y_el_texto_son_los_de_antes(pide, caso, ruta, error, codigo):
    respuesta = await pide(ruta, error)
    assert respuesta.status_code == codigo, respuesta.text
    assert respuesta.json() == {"detail": str(error)}


def test_g11_las_rutas_no_eligen_el_codigo_leyendo_el_texto_del_error():
    """
    Ningún `except ... as e` de las rutas de campos compara el error ni algo sacado de él
    (`"not found" in str(e).lower()`, o `texto = str(e).lower()` y luego `"x" in texto`).
    """
    arbol = ast.parse(RUTAS.read_text())
    lecturas = []
    for manejador in ast.walk(arbol):
        if not isinstance(manejador, ast.ExceptHandler) or manejador.name is None:
            continue
        del_error = {manejador.name}
        for nodo in ast.walk(manejador):
            if isinstance(nodo, ast.Assign) and _usa(nodo.value, del_error):
                del_error |= {t.id for t in nodo.targets if isinstance(t, ast.Name)}
        lecturas += [
            nodo.lineno
            for nodo in ast.walk(manejador)
            if isinstance(nodo, ast.Compare) and _usa(nodo, del_error)
        ]
    assert lecturas == [], f"golf_course_routes.py lee el texto del error en las líneas {lecturas}"


def _usa(nodo: ast.AST, nombres: set[str]) -> bool:
    """Si en `nodo` aparece alguno de esos nombres."""
    return any(isinstance(n, ast.Name) and n.id in nombres for n in ast.walk(nodo))
