"""
El cambio de contraseña o correo apunta la IP del cliente con la misma regla que las
demás rutas (S-15, auditoría del 18 nov 2026).

`user_routes.py` llamaba a `get_trusted_client_ip` sin `TRUST_CLOUDFLARE_HEADERS`: sin el
secreto de origen, el log de seguridad guardaba la IP del proxy. Con el secreto ya salía
bien; esto deja la ruta igual que el resto.

  B2-1 sin secreto de origen y TRUST_CLOUDFLARE_HEADERS=true -> la IP de CF-Connecting-IP
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from starlette.requests import Request
from starlette.responses import Response

from src.modules.user.application.dto.user_dto import UpdateSecurityRequestDTO
from src.modules.user.infrastructure.api.v1 import user_routes

pytestmark = pytest.mark.asyncio

PROXY = "10.0.0.7"
CLIENTE = "203.0.113.9"


def _peticion() -> Request:
    return Request(
        {
            "type": "http",
            "method": "PATCH",
            "path": "/api/v1/users/security",
            "query_string": b"",
            "headers": [(b"cf-connecting-ip", CLIENTE.encode()), (b"user-agent", b"Navegador")],
            "client": (PROXY, 443),
            "state": {},
        }
    )


async def test_b2_1_the_security_change_logs_the_cloudflare_client_ip(monkeypatch):
    """
    Given: Sin secreto de origen, con TRUST_CLOUDFLARE_HEADERS=true y CF-Connecting-IP
    When: Llega PATCH /users/security
    Then: El caso de uso recibe la IP del cliente, no la del proxy
    """
    monkeypatch.delenv("CLOUDFLARE_ORIGIN_SECRET", raising=False)
    monkeypatch.setattr(user_routes.settings, "TRUST_CLOUDFLARE_HEADERS", True)
    monkeypatch.setattr(user_routes.settings, "TRUSTED_PROXIES", [])
    monkeypatch.setattr(user_routes, "_fuera_del_limite_de_seguridad", lambda *_: None)
    caso = AsyncMock()
    caso.execute.return_value = SimpleNamespace(sesion_nueva=None)
    datos = UpdateSecurityRequestDTO(
        current_password="Contrasena-actual-1",
        new_password="Contrasena-nueva-12",
        confirm_password="Contrasena-nueva-12",
    )

    await user_routes.update_security(
        _peticion(), datos, Response(), use_case=caso, current_user=SimpleNamespace(id=uuid4())
    )

    enviado = caso.execute.await_args.args[1]
    assert enviado.ip_address == CLIENTE
