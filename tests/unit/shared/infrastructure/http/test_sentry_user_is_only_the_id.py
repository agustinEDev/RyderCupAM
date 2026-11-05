"""
A Sentry solo llega el id del usuario (revisor, 5 nov 2026).

`SentryUserContextMiddleware` mandaba también `ip_address`, sacada de
X-Forwarded-For, y `email`. El front ya manda solo el id desde el 25 oct; y la
IP del cliente no debe salir hacia Sentry (ADR-041).
"""

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.infrastructure.http import sentry_middleware
from src.shared.infrastructure.http.sentry_middleware import SentryUserContextMiddleware
from src.shared.infrastructure.security.jwt_handler import create_access_token


@pytest.fixture
def cliente():
    """Una app mínima con el middleware."""
    app = FastAPI()
    app.add_middleware(SentryUserContextMiddleware)

    @app.get("/api/v1/algo")
    async def algo():
        """Una ruta con sesión."""
        return {"ok": True}

    return TestClient(app)


def test_sentry_user_context_with_session_is_only_the_user_id(cliente):
    """
    Given: Una petición con un access token válido y X-Forwarded-For
    When: Pasa por el middleware
    Then: Sentry recibe solo el id: ni IP ni email
    """
    user_id = str(uuid4())
    token = create_access_token({"sub": user_id, "email": "ana@example.com"})

    with patch.object(sentry_middleware.sentry_sdk, "set_user") as set_user:
        cliente.get(
            "/api/v1/algo",
            headers={"cookie": f"access_token={token}", "X-Forwarded-For": "203.0.113.7"},
        )

    usuarios = [llamada.args[0] for llamada in set_user.call_args_list]
    assert {"id": user_id} in usuarios
    # Al acabar la petición se limpia (None); ninguna lleva más que el id
    assert all(u is None or set(u) == {"id"} for u in usuarios)
