"""
Rotación del refresh token con detección de robo (F-02), con la BD real.

  A1 refresco: cookie de refresco nueva (lo que le queda de los 7 días), el viejo
     sustituido en la BD con el mismo dispositivo y la misma caducidad
  A2 el viejo dentro de 60 s: 200 sin cookie de refresco nueva
  A3 el viejo fuera del margen con el sustituto sin usar: 200 con cookie nueva y el
     sustituto anulado
  A4 robo: 401 SESSION_REJECTED, cookie borrada, toda la cadena revocada y el correo
  A5 sustituido + login más nuevo en el navegador: SESSION_REPLACED, sin borrar
  A6 cerrar sesión y cambiar la contraseña tras rotar: ninguna cookie de la cadena vale
  C  dos refrescos simultáneos con la misma cookie: los dos 200, un solo sustituto
     vivo, ninguna revocación (sin robo falso)
"""

import asyncio
import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient, Response

from src.modules.user.domain.value_objects.token_hash import TokenHash
from tests.conftest import create_authenticated_user, set_auth_cookies, sql_en_la_bd_de_test

pytestmark = pytest.mark.asyncio

CLAVE = "ValidPassword123!"
SIETE_DIAS = 7 * 24 * 3600


def _cookie_de_refresco(r: Response) -> str | None:
    """El valor de la cookie de refresco que pone la respuesta, o None."""
    for k, v in r.headers.multi_items():
        if k == "set-cookie" and v.startswith("refresh_token="):
            valor = v.split(";", 1)[0].split("=", 1)[1]
            return valor or None
    return None


def _max_age_del_refresco(r: Response) -> int:
    for k, v in r.headers.multi_items():
        if k == "set-cookie" and v.startswith("refresh_token="):
            for parte in v.split(";"):
                if parte.strip().lower().startswith("max-age="):
                    return int(parte.split("=", 1)[1])
    raise AssertionError("sin Max-Age")


def _borra_la_cookie_de_refresco(r: Response) -> bool:
    return any(
        k == "set-cookie" and v.startswith("refresh_token=") and "Max-Age=0" in v
        for k, v in r.headers.multi_items()
    )


async def _sesion(client: AsyncClient, prefijo: str) -> tuple[str, dict]:
    email = f"{prefijo}-{uuid.uuid4().hex[:8]}@example.com"
    cookies = (await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez"))["cookies"]
    return email, cookies


async def _refresca(client: AsyncClient, refresco: str, **extra: str) -> Response:
    client.cookies.clear()
    set_auth_cookies(client, {"refresh_token": refresco, **extra})
    r = await client.post("/api/v1/auth/refresh-token")
    client.cookies.clear()
    return r


async def _fila(jwt: str) -> dict:
    resultado = await sql_en_la_bd_de_test(
        "SELECT id, device_id, expires_at, created_at, revoked, replaced_at, replaced_by_id "
        "FROM refresh_tokens WHERE token_hash = :h",
        h=TokenHash.from_token(jwt).value,
    )
    fila = resultado.mappings().first()
    assert fila is not None
    return dict(fila)


async def _de_su_dispositivo(device_id: str) -> list[dict]:
    resultado = await sql_en_la_bd_de_test(
        "SELECT id, revoked, replaced_at FROM refresh_tokens WHERE device_id = :d", d=device_id
    )
    return [dict(f) for f in resultado.mappings().all()]


async def _atrasa_la_sustitucion(jwt: str, tiempo: timedelta) -> None:
    await sql_en_la_bd_de_test(
        "UPDATE refresh_tokens SET replaced_at = replaced_at - make_interval(secs => :s) "
        "WHERE token_hash = :h",
        s=tiempo.total_seconds(),
        h=TokenHash.from_token(jwt).value,
    )


async def test_a1_a_refresh_rotates_the_cookie_and_keeps_the_absolute_expiry(client: AsyncClient):
    """
    Given: Una sesión recién abierta
    When: Refresca
    Then: 200 con una cookie de refresco nueva cuyo Max-Age es lo que queda de los 7
          días; en la BD el viejo queda sustituido por el nuevo, que tiene el mismo
          dispositivo y la misma caducidad; el nuevo funciona
    """
    _, cookies = await _sesion(client, "a1")

    r = await _refresca(client, cookies["refresh_token"])

    assert r.status_code == 200, r.text
    nuevo = _cookie_de_refresco(r)
    assert nuevo and nuevo != cookies["refresh_token"]
    assert "refresh_token" not in r.json()
    assert SIETE_DIAS - 60 <= _max_age_del_refresco(r) <= SIETE_DIAS
    viejo_bd, nuevo_bd = await _fila(cookies["refresh_token"]), await _fila(nuevo)
    assert viejo_bd["replaced_at"] is not None and viejo_bd["revoked"] is False
    assert viejo_bd["replaced_by_id"] == nuevo_bd["id"]
    assert nuevo_bd["device_id"] == viejo_bd["device_id"]
    assert nuevo_bd["expires_at"] == viejo_bd["expires_at"]
    assert nuevo_bd["replaced_at"] is None
    assert (await _refresca(client, nuevo)).status_code == 200


async def test_a1_a_session_with_two_days_left_gets_a_two_day_cookie(client: AsyncClient):
    """
    Given: Una sesión a la que le quedan 2 días (empezó hace 5)
    When: Refresca
    Then: La cookie nueva dura 2 días, no 7: la caducidad absoluta no se alarga
    """
    _, cookies = await _sesion(client, "a1b")
    # Como las guarda la app: hora local sin zona
    await sql_en_la_bd_de_test(
        "UPDATE refresh_tokens SET expires_at = :c WHERE token_hash = :h",
        c=datetime.now() + timedelta(days=2),
        h=TokenHash.from_token(cookies["refresh_token"]).value,
    )

    r = await _refresca(client, cookies["refresh_token"])

    assert r.status_code == 200, r.text
    dos_dias = 2 * 24 * 3600
    assert dos_dias - 120 <= _max_age_del_refresco(r) <= dos_dias + 120


async def test_a2_the_old_cookie_within_the_margin_gets_access_without_a_new_refresh(
    client: AsyncClient,
):
    """
    Given: Una pestaña acaba de refrescar (el viejo, sustituido hace un instante)
    When: La otra pestaña refresca con la misma cookie vieja
    Then: 200, access nuevo y SIN cookie de refresco: el navegador conserva la nueva
    """
    _, cookies = await _sesion(client, "a2")
    primera = await _refresca(client, cookies["refresh_token"])
    assert primera.status_code == 200

    r = await _refresca(client, cookies["refresh_token"])

    assert r.status_code == 200, r.text
    assert r.cookies.get("access_token")
    assert _cookie_de_refresco(r) is None
    assert not _borra_la_cookie_de_refresco(r)


async def test_a3_a_lost_response_is_recovered_with_the_old_cookie(client: AsyncClient):
    """
    Given: Un refresco cuya respuesta se perdió (sustituto sin usar) hace 2 minutos
    When: Llega otra vez la cookie vieja
    Then: 200 con una cookie nueva; el sustituto perdido queda anulado
    """
    _, cookies = await _sesion(client, "a3")
    perdida = _cookie_de_refresco(await _refresca(client, cookies["refresh_token"]))
    assert perdida
    await _atrasa_la_sustitucion(cookies["refresh_token"], timedelta(minutes=2))

    r = await _refresca(client, cookies["refresh_token"])

    assert r.status_code == 200, r.text
    nueva = _cookie_de_refresco(r)
    assert nueva and nueva not in (perdida, cookies["refresh_token"])
    assert (await _fila(perdida))["revoked"] is True
    assert (await _refresca(client, nueva)).status_code == 200


async def test_a4_reusing_an_old_cookie_closes_the_session_and_warns(
    client: AsyncClient, mock_external_services
):
    """
    Given: Una cookie vieja (sustituida hace 2 minutos) cuyo sustituto ya se usó
    When: Alguien refresca con ella
    Then: 401 SESSION_REJECTED con la cookie borrada; todos los tokens del dispositivo
          revocados (también el vigente) y el correo al usuario
    """
    from src.config.aviso_en_segundo_plano import espera_los_avisos_pendientes

    email, cookies = await _sesion(client, "a4")
    await sql_en_la_bd_de_test("UPDATE users SET email_verified = TRUE WHERE email = :e", e=email)
    segunda = _cookie_de_refresco(await _refresca(client, cookies["refresh_token"]))
    tercera = _cookie_de_refresco(await _refresca(client, segunda))
    assert tercera
    await _atrasa_la_sustitucion(cookies["refresh_token"], timedelta(minutes=2))

    r = await _refresca(client, cookies["refresh_token"])
    await espera_los_avisos_pendientes(tope_s=10)

    assert r.status_code == 401
    assert r.json()["error_code"] == "SESSION_REJECTED"
    assert _borra_la_cookie_de_refresco(r)
    filas = await _de_su_dispositivo(cookies["device_id"])
    assert len(filas) == 3 and all(f["revoked"] for f in filas)
    vigente = await _refresca(client, tercera)
    assert vigente.status_code == 401
    assert vigente.json()["error_code"] == "SESSION_REJECTED"
    aviso = mock_external_services.send_session_closed_for_security_notice
    aviso.assert_awaited_once()
    assert aviso.await_args.kwargs["to_email"] == email


async def test_a5_an_old_cookie_with_a_newer_login_in_the_browser_is_replaced(
    client: AsyncClient,
):
    """
    Given: La cookie vieja (sustituida hace 2 min, sustituto sin usar) y, en el mismo
           navegador, un login nuevo hace un instante
    When: Llega tarde un refresco con la vieja
    Then: 401 SESSION_REPLACED sin borrar la cookie; no se rota ni se anula nada
    """
    email, cookies = await _sesion(client, "a5")
    sustituto = _cookie_de_refresco(await _refresca(client, cookies["refresh_token"]))
    await _atrasa_la_sustitucion(cookies["refresh_token"], timedelta(minutes=2))
    client.cookies.set("device_id", cookies["device_id"])
    nuevo = await client.post("/api/v1/auth/login", json={"email": email, "password": CLAVE})
    client.cookies.clear()
    assert nuevo.status_code == 200, nuevo.text

    r = await _refresca(client, cookies["refresh_token"], device_id=cookies["device_id"])

    assert r.status_code == 401
    assert r.json()["error_code"] == "SESSION_REPLACED"
    assert not _borra_la_cookie_de_refresco(r)
    assert (await _fila(sustituto))["revoked"] is False


async def test_a6_logging_out_after_rotating_kills_every_cookie_of_the_chain(
    client: AsyncClient,
):
    """
    Given: Una sesión que ya rotó (viejo sustituido, nuevo vigente)
    When: Cierra sesión con la cookie vigente
    Then: Ni la vieja ni la vigente vuelven a valer
    """
    _, cookies = await _sesion(client, "a6")
    r = await _refresca(client, cookies["refresh_token"])
    actuales = {**cookies, **dict(r.cookies)}
    set_auth_cookies(client, actuales)
    salida = await client.post(
        "/api/v1/auth/logout", json={}, headers={"X-CSRF-Token": actuales["csrf_token"]}
    )
    client.cookies.clear()
    assert salida.status_code == 200, salida.text

    assert (await _refresca(client, cookies["refresh_token"])).status_code == 401
    assert (await _refresca(client, actuales["refresh_token"])).status_code == 401


async def test_a6_changing_the_password_after_rotating_kills_the_chain(client: AsyncClient):
    """
    Given: Una sesión que ya rotó
    When: Cambia la contraseña
    Then: Ni la vieja ni la vigente vuelven a valer
    """
    _, cookies = await _sesion(client, "a6b")
    r = await _refresca(client, cookies["refresh_token"])
    actuales = {**cookies, **dict(r.cookies)}
    set_auth_cookies(client, actuales)
    cambio = await client.patch(
        "/api/v1/users/security",
        json={
            "current_password": CLAVE,
            "new_password": "OtraValida123!",
            "confirm_password": "OtraValida123!",
        },
        headers={"X-CSRF-Token": actuales["csrf_token"]},
    )
    client.cookies.clear()
    assert cambio.status_code == 200, cambio.text

    assert (await _refresca(client, cookies["refresh_token"])).status_code == 401
    assert (await _refresca(client, actuales["refresh_token"])).status_code == 401


async def _a_la_vez(client: AsyncClient, refresco: str, veces: int) -> list[Response]:
    client.cookies.clear()
    return await asyncio.gather(
        *[
            client.post(
                "/api/v1/auth/refresh-token", headers={"Cookie": f"refresh_token={refresco}"}
            )
            for _ in range(veces)
        ]
    )


@pytest.mark.parametrize("veces", [2, 4])
async def test_c_simultaneous_refreshes_issue_a_single_substitute(client: AsyncClient, veces):
    """
    Given: Una sesión
    When: Llegan a la vez varios refrescos con la misma cookie (misma BD)
    Then: Todos 200; solo uno trae cookie de refresco nueva; en la BD hay un único
          token vivo en el dispositivo y ninguno revocado (no se detecta un robo falso)
    """
    _, cookies = await _sesion(client, "c")

    respuestas = await _a_la_vez(client, cookies["refresh_token"], veces)

    assert [r.status_code for r in respuestas] == [200] * veces
    nuevas = [c for c in (_cookie_de_refresco(r) for r in respuestas) if c]
    assert len(nuevas) == 1
    filas = await _de_su_dispositivo(cookies["device_id"])
    assert not any(f["revoked"] for f in filas)
    vivos = [f for f in filas if f["replaced_at"] is None]
    assert len(vivos) == 1
    assert (await _refresca(client, nuevas[0])).status_code == 200


async def test_c_simultaneous_retries_of_a_lost_response_issue_a_single_substitute(
    client: AsyncClient,
):
    """
    Given: Una respuesta perdida hace 2 minutos (sustituto sin usar)
    When: Llegan a la vez dos reintentos con la cookie vieja
    Then: Los dos 200 y un solo sustituto vivo nuevo; sin robo falso
    """
    _, cookies = await _sesion(client, "c3")
    await _refresca(client, cookies["refresh_token"])
    await _atrasa_la_sustitucion(cookies["refresh_token"], timedelta(minutes=2))

    respuestas = await _a_la_vez(client, cookies["refresh_token"], 2)

    assert [r.status_code for r in respuestas] == [200, 200]
    assert len([c for c in (_cookie_de_refresco(r) for r in respuestas) if c]) == 1
    filas = await _de_su_dispositivo(cookies["device_id"])
    vivos = [f for f in filas if f["replaced_at"] is None and not f["revoked"]]
    assert len(vivos) == 1


@pytest.mark.parametrize("vuelta", range(3))
async def test_c_the_old_cookie_and_its_substitute_at_once_never_leave_two_live(
    client: AsyncClient, vuelta
):
    """
    Given: Una cookie vieja sustituida hace 2 minutos, con su sustituto sin usar
    When: Llegan a la vez la vieja y el sustituto (dos sitios con la misma sesión)
    Then: Nunca quedan dos tokens vivos en el dispositivo: o la vieja reanuda y el
          sustituto llega anulado, o el sustituto rota y la vieja es un robo
    """
    _, cookies = await _sesion(client, f"c3-{vuelta}")
    sustituto = _cookie_de_refresco(await _refresca(client, cookies["refresh_token"]))
    await _atrasa_la_sustitucion(cookies["refresh_token"], timedelta(minutes=2))
    client.cookies.clear()

    await asyncio.gather(
        *[
            client.post("/api/v1/auth/refresh-token", headers={"Cookie": f"refresh_token={c}"})
            for c in (cookies["refresh_token"], sustituto)
        ]
    )

    filas = await _de_su_dispositivo(cookies["device_id"])
    vivos = [f for f in filas if f["replaced_at"] is None and not f["revoked"]]
    assert len(vivos) <= 1


# ------------------------------------------------- tras la revisión (Agustín, 10 nov)


async def _dispositivo_activo(device_id: str) -> bool:
    resultado = await sql_en_la_bd_de_test(
        "SELECT is_active FROM user_devices WHERE id = :d", d=device_id
    )
    return bool(resultado.scalar())


async def _vivos_del_usuario(email: str) -> int:
    resultado = await sql_en_la_bd_de_test(
        "SELECT count(*) FROM refresh_tokens t JOIN users u ON u.id = t.user_id "
        "WHERE u.email = :e AND NOT t.revoked AND t.replaced_at IS NULL",
        e=email,
    )
    return int(resultado.scalar())


@pytest.fixture
def refresco_lento(monkeypatch):
    """
    El refresco se para 0,3 s DENTRO de su transacción, con el sucesor ya insertado y
    sin confirmar: así la otra petición de la carrera cae siempre en el peor momento.
    """
    from src.modules.user.application.use_cases import refresh_access_token_use_case as caso

    original = caso.RefreshAccessTokenUseCase._usa_el_dispositivo
    pausa = {"s": 0.3}

    async def lento(self, request, dispositivo):
        await asyncio.sleep(pausa["s"])
        return await original(self, request, dispositivo)

    monkeypatch.setattr(caso.RefreshAccessTokenUseCase, "_usa_el_dispositivo", lento)
    return pausa


async def _despues(segundos: float, peticion):
    await asyncio.sleep(segundos)
    return await peticion


async def test_a4_the_attackers_access_token_stops_working_at_once(client: AsyncClient):
    """
    Given: El atacante tiene un access recién emitido (de la cadena robada)
    When: Se detecta el robo
    Then: Ese access da 401 al instante (el dispositivo queda revocado)
    """
    _, cookies = await _sesion(client, "a4b")
    r1 = await _refresca(client, cookies["refresh_token"])
    r2 = await _refresca(client, _cookie_de_refresco(r1))
    acceso = dict(r2.cookies)["access_token"]
    client.cookies.clear()
    set_auth_cookies(client, {"access_token": acceso})
    assert (await client.get("/api/v1/auth/current-user")).status_code == 200
    client.cookies.clear()
    await _atrasa_la_sustitucion(cookies["refresh_token"], timedelta(minutes=2))

    robo = await _refresca(client, cookies["refresh_token"])

    assert robo.status_code == 401
    assert await _dispositivo_activo(cookies["device_id"]) is False
    set_auth_cookies(client, {"access_token": acceso})
    despues = await client.get("/api/v1/auth/current-user")
    client.cookies.clear()
    assert despues.status_code == 401


async def test_a3_the_annulled_substitute_coming_back_is_a_theft(
    client: AsyncClient, mock_external_services
):
    """
    Given: Un A3 (respuesta perdida) que anuló el sustituto
    When: Llega ese sustituto
    Then: 401 SESSION_REJECTED, dispositivo revocado, nada vivo y el correo
    """
    from src.config.aviso_en_segundo_plano import espera_los_avisos_pendientes

    email, cookies = await _sesion(client, "a3b")
    await sql_en_la_bd_de_test("UPDATE users SET email_verified = TRUE WHERE email = :e", e=email)
    perdido = _cookie_de_refresco(await _refresca(client, cookies["refresh_token"]))
    await _atrasa_la_sustitucion(cookies["refresh_token"], timedelta(minutes=2))
    assert (await _refresca(client, cookies["refresh_token"])).status_code == 200

    r = await _refresca(client, perdido)
    await espera_los_avisos_pendientes(tope_s=10)

    assert r.status_code == 401
    assert r.json()["error_code"] == "SESSION_REJECTED"
    assert await _dispositivo_activo(cookies["device_id"]) is False
    assert await _vivos_del_usuario(email) == 0
    mock_external_services.send_session_closed_for_security_notice.assert_awaited_once()


@pytest.mark.parametrize("vuelta", range(3))
async def test_c_a_theft_racing_a_rotation_leaves_nothing_alive(
    client: AsyncClient, vuelta, refresco_lento
):
    """
    Given: Una cadena robada: la cookie vieja (fuera del margen) y la vigente
    When: Llegan a la vez el robo (vieja) y un refresco con la vigente
    Then: No sobrevive ningún token (tampoco uno insertado durante el A4) y el
          dispositivo queda revocado
    """
    email, cookies = await _sesion(client, f"c4-{vuelta}")
    segunda = _cookie_de_refresco(await _refresca(client, cookies["refresh_token"]))
    tercera = _cookie_de_refresco(await _refresca(client, segunda))
    await _atrasa_la_sustitucion(cookies["refresh_token"], timedelta(minutes=2))
    client.cookies.clear()

    # La rotación de la vigente empieza primero; el robo llega a mitad
    await asyncio.gather(
        client.post("/api/v1/auth/refresh-token", headers={"Cookie": f"refresh_token={tercera}"}),
        _despues(
            0.1,
            client.post(
                "/api/v1/auth/refresh-token",
                headers={"Cookie": f"refresh_token={cookies['refresh_token']}"},
            ),
        ),
    )

    assert await _vivos_del_usuario(email) == 0
    assert await _dispositivo_activo(cookies["device_id"]) is False


@pytest.mark.parametrize("vuelta", range(3))
async def test_c_logout_racing_a_refresh_leaves_nothing_alive(
    client: AsyncClient, vuelta, refresco_lento
):
    """
    Given: Una sesión
    When: Cierra sesión y, a la vez, otra pestaña refresca con la misma cookie
    Then: No queda ningún token vivo
    """
    email, cookies = await _sesion(client, f"c5-{vuelta}")
    client.cookies.clear()
    cabecera = "; ".join(f"{k}={v}" for k, v in cookies.items())

    # El refresco empieza primero; el cierre llega con el sucesor sin confirmar
    await asyncio.gather(
        client.post(
            "/api/v1/auth/refresh-token",
            headers={"Cookie": f"refresh_token={cookies['refresh_token']}"},
        ),
        _despues(
            0.1,
            client.post(
                "/api/v1/auth/logout",
                json={},
                headers={"Cookie": cabecera, "X-CSRF-Token": cookies["csrf_token"]},
            ),
        ),
    )

    assert await _vivos_del_usuario(email) == 0


@pytest.fixture
def refresco_parado_con_sus_bloqueos(monkeypatch):
    """
    El refresco se para 1,5 s con sus bloqueos ya tomados y ANTES de insertar el
    sucesor: el peor momento para un cambio de contraseña (que bloquea la cuenta).
    """
    from src.modules.user.application.use_cases import refresh_access_token_use_case as caso

    original = caso.RefreshAccessTokenUseCase._paso

    async def parado(self, *args, **kwargs):
        await asyncio.sleep(1.5)
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(caso.RefreshAccessTokenUseCase, "_paso", parado)


async def test_c_a_password_change_racing_a_refresh_leaves_nothing_alive(
    client: AsyncClient, refresco_parado_con_sus_bloqueos
):
    """
    Given: Una sesión
    When: Una pestaña refresca y, con el refresco a medias, cambia la contraseña
    Then: Ninguna de las dos falla (sin interbloqueo: los dos bloquean primero la cuenta,
          luego el dispositivo y luego los tokens) y no queda vivo ningún token de antes:
          solo la sesión nueva que el cambio da a quien lo hizo (auditoría de la fase 6,
          B-05, decidido por Agustín el 14 nov 2026)
    """
    email, cookies = await _sesion(client, "c6")
    client.cookies.clear()
    cabecera = "; ".join(f"{k}={v}" for k, v in cookies.items())

    refresco, cambio = await asyncio.gather(
        client.post(
            "/api/v1/auth/refresh-token",
            headers={"Cookie": f"refresh_token={cookies['refresh_token']}"},
        ),
        _despues(
            0.3,
            client.patch(
                "/api/v1/users/security",
                json={
                    "current_password": CLAVE,
                    "new_password": "OtraValida123!",
                    "confirm_password": "OtraValida123!",
                },
                headers={"Cookie": cabecera, "X-CSRF-Token": cookies["csrf_token"]},
            ),
        ),
        return_exceptions=True,
    )

    assert not isinstance(refresco, BaseException), refresco
    assert not isinstance(cambio, BaseException), cambio
    assert refresco.status_code < 500, refresco.text
    assert cambio.status_code == 200, cambio.text
    # Lo único vivo es la sesión nueva que el cambio puso en su respuesta
    nuevo = cambio.cookies.get("refresh_token")
    assert nuevo and nuevo != cookies["refresh_token"]
    assert await _vivos_del_usuario(email) == 1


async def test_c_logout_racing_a_password_change_does_not_deadlock(
    client: AsyncClient, monkeypatch
):
    """
    Given: Una sesión
    When: Cierra sesión y, con el cierre a medias (dispositivo y tokens ya bloqueados),
          cambia la contraseña desde otra pestaña
    Then: Las dos salen bien (sin interbloqueo: el cierre bloquea antes la cuenta, como
          los refrescos) y no queda vivo ningún token de antes: solo la sesión nueva que
          el cambio da a quien lo hizo (B-05)
    """
    from src.modules.user.infrastructure.persistence.sqlalchemy import (
        refresh_token_repository as repo,
    )

    original = repo.SQLAlchemyRefreshTokenRepository.revoke_all_for_device

    async def despacio(self, device_id):
        # Tras revocar (con las filas de los tokens ya bloqueadas) y antes de guardar el
        # usuario: el peor momento para el cambio de contraseña
        revocados = await original(self, device_id)
        await asyncio.sleep(1.5)
        return revocados

    monkeypatch.setattr(repo.SQLAlchemyRefreshTokenRepository, "revoke_all_for_device", despacio)
    email, cookies = await _sesion(client, "c7")
    client.cookies.clear()
    cabecera = "; ".join(f"{k}={v}" for k, v in cookies.items())

    salida, cambio = await asyncio.gather(
        client.post(
            "/api/v1/auth/logout",
            json={},
            headers={"Cookie": cabecera, "X-CSRF-Token": cookies["csrf_token"]},
        ),
        _despues(
            0.3,
            client.patch(
                "/api/v1/users/security",
                json={
                    "current_password": CLAVE,
                    "new_password": "OtraValida123!",
                    "confirm_password": "OtraValida123!",
                },
                headers={"Cookie": cabecera, "X-CSRF-Token": cookies["csrf_token"]},
            ),
        ),
        return_exceptions=True,
    )

    assert not isinstance(salida, BaseException), salida
    assert not isinstance(cambio, BaseException), cambio
    assert salida.status_code == 200, salida.text
    assert cambio.status_code == 200, cambio.text
    # Lo único vivo es la sesión nueva que el cambio puso en su respuesta
    nuevo = cambio.cookies.get("refresh_token")
    assert nuevo and nuevo != cookies["refresh_token"]
    assert await _vivos_del_usuario(email) == 1


async def test_c8_revoking_the_device_racing_a_refresh_does_not_deadlock(
    client: AsyncClient, monkeypatch
):
    """
    Given: Una sesión en un dispositivo, y otra en un segundo dispositivo de la cuenta
    When: Desde el segundo se revoca el primero y, con la revocación a medias (tokens ya
          bloqueados), el primero refresca
    Then: Ninguna de las dos falla (la revocación bloquea antes el dispositivo, en el
          orden de los refrescos), el dispositivo queda revocado y nada suyo vivo
    """
    from src.modules.user.infrastructure.persistence.sqlalchemy import (
        refresh_token_repository as repo,
    )

    email, cookies = await _sesion(client, "c8")
    client.cookies.clear()
    otro = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": CLAVE},
        headers={
            "X-Test-Client-ID": f"otro-{uuid.uuid4()}",
            # Otro navegador: si no, la huella lo reconoce como el mismo dispositivo
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Firefox/131.0",
        },
    )
    assert otro.status_code == 200, otro.text
    del_otro = dict(otro.cookies)
    client.cookies.clear()
    assert del_otro["device_id"] != cookies["device_id"]
    original = repo.SQLAlchemyRefreshTokenRepository.revoke_all_for_device
    a_medias = asyncio.Event()

    async def despacio(self, device_id):
        revocados = await original(self, device_id)
        a_medias.set()
        await asyncio.sleep(1.5)
        return revocados

    monkeypatch.setattr(repo.SQLAlchemyRefreshTokenRepository, "revoke_all_for_device", despacio)
    cabecera = "; ".join(f"{k}={v}" for k, v in del_otro.items())

    async def cuando_este_a_medias(peticion):
        await asyncio.wait_for(a_medias.wait(), timeout=10)
        return await peticion

    revocacion, refresco = await asyncio.gather(
        client.delete(
            f"/api/v1/users/me/devices/{cookies['device_id']}",
            headers={"Cookie": cabecera, "X-CSRF-Token": del_otro["csrf_token"]},
        ),
        cuando_este_a_medias(
            client.post(
                "/api/v1/auth/refresh-token",
                headers={"Cookie": f"refresh_token={cookies['refresh_token']}"},
            )
        ),
        return_exceptions=True,
    )

    assert not isinstance(revocacion, BaseException), revocacion
    assert not isinstance(refresco, BaseException), refresco
    assert revocacion.status_code == 200, revocacion.text
    assert refresco.status_code < 500, refresco.text
    assert await _dispositivo_activo(cookies["device_id"]) is False
    vivos = [f for f in await _de_su_dispositivo(cookies["device_id"]) if not f["revoked"]]
    assert vivos == []


async def test_row7_an_old_cookie_after_one_hour_ends_the_session_without_alarm(
    client: AsyncClient, mock_external_services
):
    """
    Given: Una cookie sustituida hace más de 1 hora cuyo sustituto nunca se usó
    When: Llega
    Then: 401 SESSION_ENDED (fin normal, sin alarma): el dispositivo sigue activo y no
          hay correo
    """
    from src.config.aviso_en_segundo_plano import espera_los_avisos_pendientes

    email, cookies = await _sesion(client, "f7")
    await sql_en_la_bd_de_test("UPDATE users SET email_verified = TRUE WHERE email = :e", e=email)
    await _refresca(client, cookies["refresh_token"])
    await _atrasa_la_sustitucion(cookies["refresh_token"], timedelta(minutes=61))

    r = await _refresca(client, cookies["refresh_token"])
    await espera_los_avisos_pendientes(tope_s=10)

    assert r.status_code == 401
    assert r.json()["error_code"] == "SESSION_ENDED"
    assert await _dispositivo_activo(cookies["device_id"]) is True
    mock_external_services.send_session_closed_for_security_notice.assert_not_awaited()
