"""
Sentry no recibe el cuerpo de ninguna petición (S-01, auditoría del 18 nov 2026).

El SDK adjuntaba el cuerpo JSON a los errores y a las transacciones, y su filtro solo
tacha claves exactas (`password`, `token`): `current_password`, `new_password` y
`new_email` salían en claro. Se apaga en el propio SDK (`max_request_body_size="never"`),
para todas las rutas: así no depende de una lista de rutas a mano.

Se prueba con el SDK de verdad, arrancado con las opciones de `init_sentry` y un
transporte que guarda lo que se enviaría:

  B1-1 un error en PATCH /users/security            -> sin cuerpo
  B1-2 la transacción del reset de contraseña        -> sin cuerpo
  B1-3 cualquier otra ruta (contacto, perfil)        -> sin cuerpo
  B1-4 lo demás del evento                           -> sigue (URL y método)
"""

import json
import logging
from typing import ClassVar

import pytest
import sentry_sdk
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.config import sentry_config

SECRETOS = ("OldSecret123!", "NewSecret456!", "victima@example.com")


class _Transporte(sentry_sdk.transport.Transport):
    """Guarda los eventos y transacciones en vez de mandarlos."""

    enviados: ClassVar[list[dict]] = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            carga = item.payload.json
            if carga:
                _Transporte.enviados.append(carga)


@pytest.fixture
def sentry_de_verdad(monkeypatch):
    """Sentry arrancado como en producción, pero sin salir a la red."""
    opciones: dict = {}
    # Nunca el Sentry de verdad: con dsn=None el SDK lee SENTRY_DSN del entorno, y el
    # .env local lleva la de producción (18 nov 2026: los tests siguientes le mandaron
    # sus errores de prueba)
    monkeypatch.setenv("SENTRY_DSN", "")
    # sentry_config.sentry_sdk es este mismo módulo: guardar el init de verdad antes
    init_de_verdad = sentry_sdk.init
    monkeypatch.setattr(sentry_config.settings, "SENTRY_DSN", "https://k@o0.ingest.example/1")
    monkeypatch.setattr(sentry_config.settings, "SENTRY_TRACES_SAMPLE_RATE", 1.0)
    monkeypatch.setattr(sentry_config.settings, "SENTRY_PROFILES_SAMPLE_RATE", 0.0)
    monkeypatch.setattr(sentry_config.sentry_sdk, "init", lambda **kw: opciones.update(kw))
    sentry_config.init_sentry()
    _Transporte.enviados = []
    init_de_verdad(**{**opciones, "transport": _Transporte})
    cliente_de_la_prueba = sentry_sdk.get_client()
    try:
        yield _Transporte.enviados
    finally:
        # Cerrar el cliente que capturó (su transporte y sus hilos), y luego apagar de
        # verdad con dsn vacío (no None, que leería SENTRY_DSN) (CodeRabbit)
        cliente_de_la_prueba.close()
        init_de_verdad(dsn="")
    # Sin transporte no sale nada a la red
    assert sentry_sdk.get_client().transport is None


def _app() -> FastAPI:
    app = FastAPI()

    @app.patch("/api/v1/users/security")
    async def seguridad(datos: dict):
        logging.getLogger("prueba").error("fallo al cambiar la contraseña")
        return {"ok": True}

    @app.post("/api/v1/auth/reset-password")
    async def reset(datos: dict):
        return {"ok": True}

    @app.post("/api/v1/support/contact")
    async def contacto(datos: dict):
        logging.getLogger("prueba").error("fallo en el contacto")
        return {"ok": True}

    @app.put("/api/v1/users/profile")
    async def perfil(datos: dict):
        logging.getLogger("prueba").error("fallo en el perfil")
        return {"ok": True}

    return app


def _cuerpos(enviados: list[dict]) -> list:
    """El cuerpo de cada envío: el SDK lo deja vacío ("") o no lo pone (None)."""
    return [(e.get("request") or {}).get("data") or None for e in enviados]


def test_b1_1_an_error_in_users_security_goes_without_the_body(sentry_de_verdad):
    """
    Given: Un error registrado durante PATCH /users/security con contraseñas y correo
    When: Sentry lo envía
    Then: El evento no lleva el cuerpo, ni ninguno de esos valores en ninguna parte
    """
    TestClient(_app()).patch(
        "/api/v1/users/security",
        json={
            "current_password": SECRETOS[0],
            "new_password": SECRETOS[1],
            "new_email": SECRETOS[2],
        },
    )
    sentry_sdk.flush()

    errores = [e for e in sentry_de_verdad if e.get("type") != "transaction"]
    assert errores, "el error tenía que llegar"
    assert _cuerpos(sentry_de_verdad) == [None] * len(sentry_de_verdad)
    for secreto in SECRETOS:
        assert secreto not in json.dumps(sentry_de_verdad)


def test_b1_2_the_reset_transaction_goes_without_the_body(sentry_de_verdad):
    """
    Given: POST /auth/reset-password con la contraseña nueva (sin error: solo transacción)
    When: Sentry envía la transacción
    Then: Sin el cuerpo
    """
    TestClient(_app()).post(
        "/api/v1/auth/reset-password", json={"token": "t" * 40, "new_password": SECRETOS[1]}
    )
    sentry_sdk.flush()

    transacciones = [e for e in sentry_de_verdad if e.get("type") == "transaction"]
    assert transacciones, "la transacción tenía que llegar"
    assert SECRETOS[1] not in json.dumps(sentry_de_verdad)
    assert _cuerpos(transacciones) == [None] * len(transacciones)


@pytest.mark.parametrize(
    ("metodo", "ruta"), [("post", "/api/v1/support/contact"), ("put", "/api/v1/users/profile")]
)
def test_b1_3_any_other_route_goes_without_the_body(sentry_de_verdad, metodo, ruta):
    """
    Given: Un error en cualquier otra ruta con datos personales en el cuerpo
    When: Sentry lo envía
    Then: Sin el cuerpo
    """
    getattr(TestClient(_app()), metodo)(ruta, json={"nombre": "Ana", "correo": SECRETOS[2]})
    sentry_sdk.flush()

    # Un error de verdad, no solo la transacción (CodeRabbit: con trazas al 100 %, la
    # transacción sola dejaba pasar el test aunque los errores no se capturaran)
    assert [e for e in sentry_de_verdad if e.get("type") != "transaction"]
    assert SECRETOS[2] not in json.dumps(sentry_de_verdad)
    assert _cuerpos(sentry_de_verdad) == [None] * len(sentry_de_verdad)


def test_b1_4_the_rest_of_the_request_is_kept(sentry_de_verdad):
    """
    Given: Un error en PATCH /users/security
    When: Sentry lo envía
    Then: Sigue llevando la URL y el método, para saber dónde pasó
    """
    TestClient(_app()).patch("/api/v1/users/security", json={"new_password": SECRETOS[1]})
    sentry_sdk.flush()

    error = next(e for e in sentry_de_verdad if e.get("type") != "transaction")
    assert error["request"]["method"] == "PATCH"
    assert error["request"]["url"].endswith("/api/v1/users/security")


def test_the_test_suite_never_has_the_real_sentry_dsn():
    """
    Given: Los tests (conftest.py)
    When: Se mira SENTRY_DSN y el cliente de Sentry fuera de este fichero
    Then: Vacía y el cliente sin transporte: un init(dsn=None) no encontraría la de producción
    """
    import os

    assert os.environ.get("SENTRY_DSN") == ""
    # Sin transporte no sale nada a la red
    assert sentry_sdk.get_client().transport is None
