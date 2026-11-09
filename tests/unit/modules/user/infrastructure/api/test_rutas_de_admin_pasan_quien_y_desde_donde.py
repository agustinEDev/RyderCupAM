"""
Las rutas de administrador pasan al caso de uso quién lo hace y desde dónde (F-20),
para el log de seguridad: editar un usuario y borrarlo, como ya hacía (des)activar.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from starlette.requests import Request

from src.modules.user.application.dto.admin_dto import AdminUpdateUserRequestDTO
from src.modules.user.infrastructure.api.v1 import admin_routes

pytestmark = pytest.mark.asyncio

IP = "198.51.100.4"
NAVEGADOR = "Navegador del admin"


def _peticion() -> Request:
    """Una petición desde la IP del administrador, con su navegador."""
    return Request(
        {
            "type": "http",
            "method": "PUT",
            "path": "/api/v1/admin/users/x",
            "query_string": b"",
            "headers": [(b"user-agent", NAVEGADOR.encode())],
            "client": (IP, 12345),
        }
    )


def _admin() -> SimpleNamespace:
    """El administrador de la sesión."""
    return SimpleNamespace(id=uuid4(), is_admin=True)


async def test_editing_a_user_passes_the_actor_ip_and_browser():
    """
    Given: Un administrador que edita una cuenta
    When: Llega PUT /admin/users/{id}
    Then: El caso de uso recibe al administrador, su IP y su navegador
    """
    admin = _admin()
    caso = AsyncMock()

    await admin_routes.update_user(
        _peticion(),
        "cuenta-1",
        AdminUpdateUserRequestDTO(is_admin=True),
        current_user=admin,
        use_case=caso,
    )

    datos = caso.execute.await_args.kwargs
    assert (datos["actor_user_id"], datos["ip_address"], datos["user_agent"]) == (
        str(admin.id),
        IP,
        NAVEGADOR,
    )


async def test_deleting_a_user_passes_the_actor_ip_and_browser():
    """
    Given: Un administrador que borra otra cuenta
    When: Llega DELETE /admin/users/{id}
    Then: El caso de uso recibe al administrador, su IP y su navegador
    """
    admin = _admin()
    caso = AsyncMock()

    await admin_routes.delete_user(_peticion(), "cuenta-1", current_user=admin, use_case=caso)

    datos = caso.execute.await_args.kwargs
    assert (datos["actor_user_id"], datos["ip_address"], datos["user_agent"]) == (
        str(admin.id),
        IP,
        NAVEGADOR,
    )
