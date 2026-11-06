"""
Desbloquear una cuenta es solo de administradores (hotfix 2.50.1).

Hasta la 2.50.0, `/unlock-account` solo pedía sesión: cualquier usuario podía quitar
el bloqueo por fallos de otra cuenta y seguir probando contraseñas contra ella
(auditoría OWASP de BE #732, A01/A07).

  #   caso                                        | esperado
  ----|--------------------------------------------|----------------------------------
  U1  un usuario normal desbloquea otra cuenta      | 403, y la cuenta sigue bloqueada
  U2  un usuario normal intenta su propia cuenta    | 403
  U2b un usuario normal con un id que no existe     | 403 también: no dice si existe
  U3  un administrador desbloquea                   | 200, y la dueña ya puede entrar
  U4  el intento sin permiso y el desbloqueo        | los dos quedan en el log de seguridad
  U5  el log falla con un no administrador          | 403 igual, no 500
  U6  el cuerpo dice que desbloquea otro admin      | se apunta al que llama, no al del cuerpo
"""

import uuid

import pytest
from httpx import AsyncClient

from src.config.rate_limit import limiter
from tests.conftest import create_admin_user, create_authenticated_user, set_auth_cookies

pytestmark = pytest.mark.asyncio

CLAVE = "ValidPassword123!"
SIN_PERMISO = "You do not have administrator privileges"


@pytest.fixture(autouse=True)
def sin_cupo_por_minuto():
    """Para llegar al bloqueo sin chocar con el límite de intentos por minuto."""
    previous = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = previous


def _email(prefijo: str) -> str:
    return f"{prefijo}-{uuid.uuid4().hex[:8]}@example.com"


async def _bloqueada(client: AsyncClient) -> dict:
    """Una cuenta bloqueada por fallos."""
    victima = await create_authenticated_user(client, _email("victima"), CLAVE, "Vic", "Tima")
    for i in range(10):
        await client.post(
            "/api/v1/auth/login",
            json={"email": victima["user"]["email"], "password": "WrongPassword123!"},
            headers={"X-Test-Client-ID": f"bloqueo-{i}"},
        )
    client.cookies.clear()
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": victima["user"]["email"], "password": CLAVE},
        headers={"X-Test-Client-ID": "comprueba"},
    )
    assert r.status_code == 423, r.text
    client.cookies.clear()
    return victima


async def _desbloquea(client: AsyncClient, quien: dict, user_id: str, firma: str | None = None):
    set_auth_cookies(client, quien["cookies"])
    r = await client.post(
        "/api/v1/auth/unlock-account",
        # El contrato lo pide, pero la ruta pone siempre a quien llama
        json={"user_id": user_id, "unlocked_by_user_id": firma or quien["user"]["id"]},
        headers={"X-CSRF-Token": quien["cookies"].get("csrf_token", "")},
    )
    client.cookies.clear()
    return r


async def _entra(client: AsyncClient, email: str):
    client.cookies.clear()
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": CLAVE},
        headers={"X-Test-Client-ID": f"entra-{uuid.uuid4().hex[:6]}"},
    )
    client.cookies.clear()
    return r


async def test_u1_un_usuario_normal_no_desbloquea_otra_cuenta(client: AsyncClient):
    """
    Given: Una cuenta bloqueada por fallos, y otro usuario cualquiera con sesión
    When: Ese usuario la desbloquea
    Then: 403, y la cuenta sigue bloqueada
    """
    victima = await _bloqueada(client)
    atacante = await create_authenticated_user(client, _email("atacante"), CLAVE, "Ata", "Cante")

    r = await _desbloquea(client, atacante, victima["user"]["id"])

    assert r.status_code == 403, r.text
    assert r.json()["detail"] == SIN_PERMISO
    assert (await _entra(client, victima["user"]["email"])).status_code == 423


async def test_u2_un_usuario_normal_tampoco_su_propia_cuenta(client: AsyncClient):
    """
    Given: Un usuario normal con sesión
    When: Pide desbloquear su propia cuenta
    Then: 403
    """
    yo = await create_authenticated_user(client, _email("yo"), CLAVE, "Yo", "Mismo")

    r = await _desbloquea(client, yo, yo["user"]["id"])

    assert r.status_code == 403, r.text
    assert r.json()["detail"] == SIN_PERMISO


async def test_u2b_un_id_que_no_existe_tambien_da_403(client: AsyncClient):
    """
    Given: Un usuario normal con sesión
    When: Pide desbloquear un id que no existe
    Then: 403, no 400: el permiso se mira antes de buscar la cuenta
    """
    yo = await create_authenticated_user(client, _email("yo"), CLAVE, "Yo", "Mismo")

    r = await _desbloquea(client, yo, str(uuid.uuid4()))

    assert r.status_code == 403, r.text
    assert r.json()["detail"] == SIN_PERMISO


async def test_u3_un_administrador_desbloquea(client: AsyncClient):
    """
    Given: Una cuenta bloqueada por fallos y un administrador
    When: El administrador la desbloquea
    Then: 200, y la dueña ya puede entrar
    """
    victima = await _bloqueada(client)
    admin = await create_admin_user(client, _email("admin"), CLAVE, "Ad", "Min")

    r = await _desbloquea(client, admin, victima["user"]["id"])

    assert r.status_code == 200, r.text
    assert (await _entra(client, victima["user"]["email"])).status_code == 200


async def test_u4_el_intento_sin_permiso_y_el_desbloqueo_quedan_en_el_log(
    client: AsyncClient, monkeypatch
):
    """
    Given: Una cuenta bloqueada, un usuario normal y un administrador
    When: El normal intenta desbloquearla y luego la desbloquea el administrador
    Then: El log de seguridad recibe el acceso denegado y el desbloqueo, con quién
    """
    from src.shared.infrastructure.logging.security_logger import SecurityLogger

    denegados, desbloqueos = [], []
    monkeypatch.setattr(
        SecurityLogger, "log_access_denied", lambda self, **kw: denegados.append(kw)
    )
    monkeypatch.setattr(
        SecurityLogger, "log_account_unlocked", lambda self, **kw: desbloqueos.append(kw)
    )
    victima = await _bloqueada(client)
    atacante = await create_authenticated_user(client, _email("atacante"), CLAVE, "Ata", "Cante")
    admin = await create_admin_user(client, _email("admin"), CLAVE, "Ad", "Min")

    await _desbloquea(client, atacante, victima["user"]["id"])
    await _desbloquea(client, admin, victima["user"]["id"])

    assert [(d["user_id"], d["action_attempted"], d["denial_reason"]) for d in denegados] == [
        (atacante["user"]["id"], "unlock", "not_admin")
    ]
    assert [(d["user_id"], d["unlocked_user_id"]) for d in desbloqueos] == [
        (admin["user"]["id"], victima["user"]["id"])
    ]
    assert desbloqueos[0]["previous_failed_attempts"] == 10


async def test_u5_si_falla_el_log_el_no_administrador_sigue_recibiendo_403(
    client: AsyncClient, monkeypatch
):
    """
    Given: Un usuario normal, y el log de seguridad que falla al escribir
    When: Intenta desbloquear una cuenta
    Then: 403, no 500: el log nunca cambia la respuesta
    """
    from src.shared.infrastructure.logging.security_logger import SecurityLogger

    def roto(self, **kw):
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(SecurityLogger, "log_access_denied", roto)
    yo = await create_authenticated_user(client, _email("yo"), CLAVE, "Yo", "Mismo")

    r = await _desbloquea(client, yo, yo["user"]["id"])

    assert r.status_code == 403, r.text


async def test_u6_quien_desbloquea_sale_de_la_sesion_no_del_cuerpo(
    client: AsyncClient, monkeypatch
):
    """
    Given: Una cuenta bloqueada y un administrador
    When: Desbloquea mandando en el cuerpo el id de otra persona como autor
    Then: La respuesta y el log apuntan al administrador que llama
    """
    from src.shared.infrastructure.logging.security_logger import SecurityLogger

    desbloqueos = []
    monkeypatch.setattr(
        SecurityLogger, "log_account_unlocked", lambda self, **kw: desbloqueos.append(kw)
    )
    victima = await _bloqueada(client)
    admin = await create_admin_user(client, _email("admin"), CLAVE, "Ad", "Min")

    r = await _desbloquea(client, admin, victima["user"]["id"], firma=str(uuid.uuid4()))

    assert r.status_code == 200, r.text
    assert r.json()["unlocked_by"] == admin["user"]["id"]
    assert desbloqueos[0]["user_id"] == admin["user"]["id"]
