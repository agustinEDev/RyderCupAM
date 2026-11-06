"""
Cuentas desactivadas sin sesión (BE #744) y los dos códigos del refresco (BE #733).

  #   caso                                                | esperado
  ----|----------------------------------------------------|------------------------------
  A1  un administrador desactiva a Ana                    | la siguiente petición de Ana con
                                                          |   su token de acceso: 401
  A2  y su refresco                                       | 401 SESSION_REJECTED
  A3  un administrador desactivado                        | ya no pasa las rutas de admin
  A4  la reactivan                                        | su sesión vieja no vuelve: 401
  C1  un token revocado y uno que ya no existe            | la misma respuesta: no dice si la
                                                          |   cuenta se borró o cerró sesión
  C2  el motivo exacto                                    | va al log de seguridad
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from main import app as fastapi_app
from src.config.dependencies import get_db_session
from tests.conftest import create_admin_user, create_authenticated_user, set_auth_cookies

pytestmark = pytest.mark.asyncio

CLAVE = "ValidPassword123!"


def _email(prefijo: str) -> str:
    return f"{prefijo}-{uuid.uuid4().hex[:8]}@example.com"


async def _sql(sentencia: str, **parametros):
    override = fastapi_app.dependency_overrides[get_db_session]
    async for sesion in override():
        resultado = await sesion.execute(text(sentencia), parametros)
        await sesion.commit()
        return resultado
    return None


async def _desactiva(client: AsyncClient, admin: dict, user_id: str, activa: bool = False):
    set_auth_cookies(client, admin["cookies"])
    r = await client.put(
        f"/api/v1/admin/users/{user_id}/active",
        json={"is_active": activa},
        headers={"X-CSRF-Token": admin["cookies"].get("csrf_token", "")},
    )
    client.cookies.clear()
    assert r.status_code in (200, 204), r.text


async def _yo(client: AsyncClient, quien: dict):
    set_auth_cookies(client, quien["cookies"])
    r = await client.get("/api/v1/auth/current-user")
    client.cookies.clear()
    return r


async def _refresca(client: AsyncClient, quien: dict):
    set_auth_cookies(client, quien["cookies"])
    r = await client.post("/api/v1/auth/refresh-token")
    client.cookies.clear()
    return r


async def test_a1_a2_la_cuenta_desactivada_se_queda_sin_sesion_al_momento(client: AsyncClient):
    """
    Given: Ana con sesión, y un administrador
    When: El administrador la desactiva
    Then: Su token de acceso, aún sin caducar, da 401; y su refresco, SESSION_REJECTED
    """
    ana = await create_authenticated_user(client, _email("ana"), CLAVE, "Ana", "Baja")
    admin = await create_admin_user(client, _email("admin"), CLAVE, "Ad", "Min")
    assert (await _yo(client, ana)).status_code == 200

    await _desactiva(client, admin, ana["user"]["id"])

    assert (await _yo(client, ana)).status_code == 401
    r = await _refresca(client, ana)
    assert r.status_code == 401
    assert r.json()["error_code"] == "SESSION_REJECTED"


async def test_a3_un_administrador_desactivado_ya_no_pasa_las_rutas_de_admin(client: AsyncClient):
    """
    Given: Dos administradores
    When: Uno desactiva al otro
    Then: El desactivado recibe 401 en una ruta de administración
    """
    jefe = await create_admin_user(client, _email("jefe"), CLAVE, "Je", "Fe")
    otro = await create_admin_user(client, _email("otro"), CLAVE, "Ot", "Ro")

    await _desactiva(client, jefe, otro["user"]["id"])

    set_auth_cookies(client, otro["cookies"])
    r = await client.get("/api/v1/admin/stats")
    client.cookies.clear()
    assert r.status_code == 401


async def test_a4_reactivar_no_devuelve_la_sesion_vieja(client: AsyncClient):
    """
    Given: Ana desactivada
    When: La reactivan
    Then: Su sesión vieja sigue sin valer: tiene que entrar otra vez
    """
    ana = await create_authenticated_user(client, _email("ana"), CLAVE, "Ana", "Vuelve")
    admin = await create_admin_user(client, _email("admin"), CLAVE, "Ad", "Min")
    await _desactiva(client, admin, ana["user"]["id"])

    await _desactiva(client, admin, ana["user"]["id"], activa=True)

    assert (await _yo(client, ana)).status_code == 401
    assert (await _refresca(client, ana)).status_code == 401


async def test_c1_revocado_y_borrado_responden_igual(client: AsyncClient):
    """
    Given: Una sesión revocada (cerró sesión) y otra cuyo token ya no existe
    When: Refrescan
    Then: Las dos responden lo mismo: 401, el mismo texto y SESSION_REJECTED
    """
    revocada = await create_authenticated_user(client, _email("rev"), CLAVE, "Re", "Vocada")
    set_auth_cookies(client, revocada["cookies"])
    salida = await client.post(
        "/api/v1/auth/logout",
        json={},
        headers={"X-CSRF-Token": revocada["cookies"].get("csrf_token", "")},
    )
    client.cookies.clear()
    assert salida.status_code == 200, salida.text
    borrada = await create_authenticated_user(client, _email("bor"), CLAVE, "Bo", "Rrada")
    await _sql("delete from refresh_tokens where user_id = :u", u=borrada["user"]["id"])

    r1 = await _refresca(client, revocada)
    r2 = await _refresca(client, borrada)

    assert (r1.status_code, r1.json()) == (r2.status_code, r2.json())
    assert r1.json()["error_code"] == "SESSION_REJECTED"


async def test_c2_el_motivo_exacto_va_al_log_de_seguridad(client: AsyncClient, monkeypatch):
    """
    Given: Una sesión cuyo token ya no existe
    When: Refresca
    Then: El cliente ve SESSION_REJECTED; el log de seguridad, REFRESH_TOKEN_NOT_FOUND
    """
    from src.shared.infrastructure.logging.security_logger import SecurityLogger

    apuntados = []
    monkeypatch.setattr(
        SecurityLogger, "log_refresh_rejected", lambda self, **kw: apuntados.append(kw)
    )
    yo = await create_authenticated_user(client, _email("log"), CLAVE, "Luis", "Garcia")
    await _sql("delete from refresh_tokens where user_id = :u", u=yo["user"]["id"])

    r = await _refresca(client, yo)

    assert r.json()["error_code"] == "SESSION_REJECTED"
    assert [(a["reason"], a["rejected"]) for a in apuntados] == [("REFRESH_TOKEN_NOT_FOUND", True)]
