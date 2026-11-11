"""
Registro sin enumeración, enlaces con hash y caducidad, y freno del restablecer (fase 3,
F-01/F-04/F-05/F-10/F-13; tabla aprobada por Agustín).

  #   Caso                                           | Resultado
  ----|-----------------------------------------------|---------------------------------
  B1  correo nuevo                                   | 201 con el usuario + verificación
  B2  correo de cuenta verificada                    | 201 con la MISMA forma y datos;
                                                     |   la cuenta intacta; aviso al dueño
  B2  otra vez dentro de las 24 h                    | 201 igual, sin otro aviso
  B3  correo de cuenta sin verificar                 | 201 igual; el mismo aviso, sin
                                                     |   reenviar la verificación
  C1  verificar con enlace caducado (> 48 h)         | 400 VERIFICATION_TOKEN_EXPIRED
  C1  verificar con enlace que no es                 | 400 sin ese código, como siempre
  C3  la BD guarda el SHA-256 de los dos enlaces     | y el enlace del correo funciona
  C3  token en claro de antes (verificar / reset)    | enlace no válido
  C2  restablecer pasada 1 h                         | 400 RESET_TOKEN_INVALID
  C2  pedir otro enlace anula el anterior; uso único | 400 RESET_TOKEN_INVALID
  C4  POST /validate-reset-token con el cuerpo       | valid True / False (el GET se
                                                     |   quitó en la 2.58.0)
  H1  forgot-password 3/hora por correo + red        | la 4.ª de esa red 429; otra red, 200
  H2  11.º correo de reset del día (redes distintas) | 200 igual, sin correo
  H3  correo sin cuenta                              | la misma respuesta
  M2  iniciar sesión con contraseña                  | el cupo de 10 vuelve a cero
"""

import uuid

import pytest
from httpx import AsyncClient

from src.config.aviso_en_segundo_plano import espera_los_avisos_pendientes
from src.modules.user.domain.value_objects.token_hash import hash_del_enlace
from tests.conftest import get_user_by_email, sql_en_la_bd_de_test

pytestmark = pytest.mark.asyncio

CLAVE_DEL_DUENO = "Du3n0$ecureP@ss"
CLAVE_DEL_OTRO = "V@l1dP@ss123!"
NUEVA = "N3wS3cur3P@ss!"


def _sha(token: str) -> str:
    """El hash de un enlace, con el helper de producción (sin hashlib en los tests)."""
    return hash_del_enlace(token)


def _correo() -> str:
    return f"f3-{uuid.uuid4().hex[:10]}@example.com"


def _red(nombre: str) -> dict:
    return {"X-Test-Client-ID": f"{nombre}-{uuid.uuid4().hex[:6]}"}


async def _registra(client: AsyncClient, email: str, clave=CLAVE_DEL_OTRO, nombre="Otro"):
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": clave,
            "first_name": nombre,
            "last_name": "Nombre",
            "accept_terms": True,
        },
        headers=_red("alta"),
    )
    await espera_los_avisos_pendientes(tope_s=10)
    client.cookies.clear()
    return r


def _token_de_verificacion(mock, email: str) -> str:
    llamadas = [
        c for c in mock.send_verification_email.await_args_list if c.kwargs["to_email"] == email
    ]
    return llamadas[-1].kwargs["verification_token"]


def _token_de_reset(mock, email: str) -> str:
    llamadas = [
        c for c in mock.send_password_reset_email.await_args_list if c.kwargs["to_email"] == email
    ]
    return llamadas[-1].kwargs["reset_link"].rsplit("/", 1)[1]


def _avisos_a(mock, email: str) -> int:
    return sum(
        1
        for c in mock.send_register_attempt_notice.await_args_list
        if c.kwargs["to_email"] == email
    )


async def _dueno_verificado(client: AsyncClient, mock) -> str:
    email = _correo()
    assert (await _registra(client, email, CLAVE_DEL_DUENO, "Ana")).status_code == 201
    r = await client.post(
        "/api/v1/auth/verify-email", json={"token": _token_de_verificacion(mock, email)}
    )
    assert r.status_code == 200, r.text
    return email


def _sin_lo_propio(cuerpo: dict) -> dict:
    return {k: v for k, v in cuerpo.items() if k not in ("id", "created_at", "updated_at")}


async def _pide_reset(client: AsyncClient, email: str, red: dict):
    r = await client.post("/api/v1/auth/forgot-password", json={"email": email}, headers=red)
    # El correo sale en segundo plano (fase 3, B-2)
    await espera_los_avisos_pendientes(tope_s=10)
    return r


# --- B: el registro -------------------------------------------------------------------


async def test_b1_b2_b3_the_three_answers_are_the_same(client: AsyncClient, mock_external_services):
    """
    Given: Un correo nuevo, uno de una cuenta verificada y uno de una sin verificar
    When: Otro se registra con cada uno con los mismos datos
    Then: 201 con la misma forma y los mismos datos (salvo id y fechas)
    """
    verificado = await _dueno_verificado(client, mock_external_services)
    sin_verificar = _correo()
    assert (await _registra(client, sin_verificar, CLAVE_DEL_DUENO, "Ana")).status_code == 201

    respuestas = {
        "B1": await _registra(client, _correo()),
        "B2": await _registra(client, verificado),
        "B3": await _registra(client, sin_verificar),
    }

    assert {k: r.status_code for k, r in respuestas.items()} == dict.fromkeys(respuestas, 201)
    cuerpos = {k: r.json() for k, r in respuestas.items()}
    assert {k: sorted(c) for k, c in cuerpos.items()} == dict.fromkeys(
        respuestas, sorted(cuerpos["B1"])
    )
    for k in ("B2", "B3"):
        sin_email = {**_sin_lo_propio(cuerpos[k]), "email": None}
        assert sin_email == {**_sin_lo_propio(cuerpos["B1"]), "email": None}, k
    assert cuerpos["B2"]["first_name"] == "Otro" and cuerpos["B2"]["email_verified"] is False


async def test_b2_the_account_is_untouched_and_the_owner_gets_one_notice(
    client: AsyncClient, mock_external_services
):
    """
    Given: Una cuenta verificada
    When: Otro se registra dos veces con su correo
    Then: El dueño sigue entrando con su contraseña (la otra no vale), su id no cambia,
          un solo aviso y ningún correo de verificación nuevo
    """
    email = await _dueno_verificado(client, mock_external_services)
    antes = await get_user_by_email(client, email)
    verificaciones = mock_external_services.send_verification_email.await_count

    r1 = await _registra(client, email)
    r2 = await _registra(client, email)

    assert r1.json()["id"] != str(antes.id.value) and r2.json()["id"] != r1.json()["id"]
    despues = await get_user_by_email(client, email)
    assert despues.id == antes.id and despues.first_name == "Ana" and despues.email_verified
    assert _avisos_a(mock_external_services, email) == 1
    assert mock_external_services.send_verification_email.await_count == verificaciones
    entra = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": CLAVE_DEL_DUENO}
    )
    assert entra.status_code == 200
    client.cookies.clear()
    otro = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": CLAVE_DEL_OTRO},
        headers=_red("login-otro"),
    )
    assert otro.status_code == 401


async def test_b2_a_day_later_the_owner_gets_another_notice(
    client: AsyncClient, mock_external_services
):
    """
    Given: Una cuenta verificada que recibió el aviso hace 25 h
    When: Otro se registra con su correo
    Then: Otro aviso
    """
    email = await _dueno_verificado(client, mock_external_services)
    await _registra(client, email)
    await sql_en_la_bd_de_test(
        "update users set register_attempt_notice_at = now() - interval '25 hours' "
        "where email = :e",
        e=email,
    )

    await _registra(client, email)

    assert _avisos_a(mock_external_services, email) == 2


async def test_b3_an_unverified_account_gets_the_notice_not_a_new_link(
    client: AsyncClient, mock_external_services
):
    """
    Given: Una cuenta sin verificar
    When: Otro se registra dos veces con su correo
    Then: Un solo aviso y ninguna verificación nueva; la cuenta, igual (su enlace sigue)
    """
    email = _correo()
    await _registra(client, email, CLAVE_DEL_DUENO, "Ana")
    enlace = _token_de_verificacion(mock_external_services, email)
    verificaciones = mock_external_services.send_verification_email.await_count

    r = await _registra(client, email)
    await _registra(client, email)

    assert r.status_code == 201
    assert mock_external_services.send_verification_email.await_count == verificaciones
    assert _avisos_a(mock_external_services, email) == 1
    assert (await get_user_by_email(client, email)).first_name == "Ana"
    verifica = await client.post("/api/v1/auth/verify-email", json={"token": enlace})
    assert verifica.status_code == 200, verifica.text


# --- C: los enlaces ---------------------------------------------------------------------


async def test_c3_the_db_keeps_the_hash_and_the_mailed_link_verifies(
    client: AsyncClient, mock_external_services
):
    """
    Given: Un alta
    When: Se mira la BD y se usa el enlace del correo
    Then: La BD guarda el SHA-256 con su caducidad; el enlace verifica
    """
    email = _correo()
    await _registra(client, email)
    token = _token_de_verificacion(mock_external_services, email)

    fila = (
        await sql_en_la_bd_de_test(
            "select verification_token, verification_token_expires_at - created_at "
            "from users where email = :e",
            e=email,
        )
    ).one()

    assert fila[0] == _sha(token)
    assert abs(fila[1].total_seconds() - 48 * 3600) < 60
    r = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert r.status_code == 200, r.text


async def test_c1_an_expired_verification_link_says_so(client: AsyncClient, mock_external_services):
    """
    Given: Un enlace de verificación caducado
    When: Se usa
    Then: 400 con error_code VERIFICATION_TOKEN_EXPIRED
    """
    email = _correo()
    await _registra(client, email)
    await sql_en_la_bd_de_test(
        "update users set verification_token_expires_at = now() - interval '1 minute' "
        "where email = :e",
        e=email,
    )

    r = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": _token_de_verificacion(mock_external_services, email)},
    )

    assert r.status_code == 400
    assert r.json()["error_code"] == "VERIFICATION_TOKEN_EXPIRED"
    assert not (await get_user_by_email(client, email)).email_verified


@pytest.mark.parametrize("cual", ["otro token", "en claro de antes"])
async def test_c1_c3_an_invalid_verification_link_is_not_expired(client: AsyncClient, cual):
    """
    Given: Un token que no es, o el token en claro guardado antes del cambio
    When: Se usa
    Then: 400 de enlace no válido, sin el código de caducado
    """
    email = _correo()
    await _registra(client, email)
    token = "token-en-claro-de-antes-0123456789abcdef0123"
    if cual == "en claro de antes":
        await sql_en_la_bd_de_test(
            "update users set verification_token = :t where email = :e", t=token, e=email
        )

    r = await client.post("/api/v1/auth/verify-email", json={"token": token})

    assert r.status_code == 400
    assert r.json().get("error_code") != "VERIFICATION_TOKEN_EXPIRED"


async def test_c2_c3_reset_link_hashed_one_hour_and_used_once(
    client: AsyncClient, mock_external_services
):
    """
    Given: Una cuenta que pide restablecer
    When: Se mira la BD, se usa el enlace dos veces
    Then: BD con el SHA-256 y 1 h; la primera cambia la contraseña, la segunda 400
    """
    email = _correo()
    await _registra(client, email)
    await _pide_reset(client, email, _red("reset"))
    token = _token_de_reset(mock_external_services, email)
    fila = (
        await sql_en_la_bd_de_test(
            "select password_reset_token, reset_token_expires_at - updated_at "
            "from users where email = :e",
            e=email,
        )
    ).one()
    assert fila[0] == _sha(token)
    assert abs(fila[1].total_seconds() - 3600) < 60

    primera = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": NUEVA}
    )
    segunda = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "Otr4S3cur3P@ss!"}
    )

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 400
    assert segunda.json()["error_code"] == "RESET_TOKEN_INVALID"


async def test_c2_a_new_reset_link_voids_the_previous_one(
    client: AsyncClient, mock_external_services
):
    """
    Given: Dos enlaces de restablecer seguidos
    When: Se usa el primero
    Then: 400 RESET_TOKEN_INVALID; el segundo vale
    """
    email = _correo()
    await _registra(client, email)
    await _pide_reset(client, email, _red("reset"))
    primero = _token_de_reset(mock_external_services, email)
    await _pide_reset(client, email, _red("reset"))
    segundo = _token_de_reset(mock_external_services, email)

    r1 = await client.post(
        "/api/v1/auth/reset-password", json={"token": primero, "new_password": NUEVA}
    )
    r2 = await client.post(
        "/api/v1/auth/reset-password", json={"token": segundo, "new_password": NUEVA}
    )

    assert r1.status_code == 400 and r1.json()["error_code"] == "RESET_TOKEN_INVALID"
    assert r2.status_code == 200, r2.text


async def test_c2_a_reset_link_older_than_one_hour_is_refused(
    client: AsyncClient, mock_external_services
):
    """
    Given: Un enlace de restablecer cuya hora ya pasó
    When: Se usa
    Then: 400 RESET_TOKEN_INVALID
    """
    email = _correo()
    await _registra(client, email)
    await _pide_reset(client, email, _red("reset"))
    await sql_en_la_bd_de_test(
        "update users set reset_token_expires_at = now() - interval '1 second' where email = :e",
        e=email,
    )

    r = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": _token_de_reset(mock_external_services, email), "new_password": NUEVA},
    )

    assert r.status_code == 400 and r.json()["error_code"] == "RESET_TOKEN_INVALID"


async def test_c4_validate_by_post_with_the_token_in_the_body(
    client: AsyncClient, mock_external_services
):
    """
    Given: Un enlace de restablecer vigente
    When: Se valida por POST con el token en el cuerpo (y con tokens que no son)
    Then: valid True con el bueno; False con otro, con uno de longitud imposible y con
          el token en claro guardado antes del cambio
    """
    email = _correo()
    await _registra(client, email)
    await _pide_reset(client, email, _red("reset"))
    token = _token_de_reset(mock_external_services, email)

    async def valida(t: str) -> bool:
        r = await client.post("/api/v1/auth/validate-reset-token", json={"token": t})
        assert r.status_code == 200, r.text
        return r.json()["valid"]

    assert await valida(token) is True
    assert await valida("x" * 43) is False
    assert await valida("corto") is False
    viejo = "reset-en-claro-de-antes-0123456789abcdef012"
    await sql_en_la_bd_de_test(
        "update users set password_reset_token = :t where email = :e", t=viejo, e=email
    )
    assert await valida(viejo) is False


# --- H: el freno de «Olvidé mi contraseña» ----------------------------------------------


async def test_h1_three_per_hour_per_email_and_network(client: AsyncClient):
    """
    Given: Un correo
    When: Se pide 4 veces desde una red, y otra desde otra red
    Then: La 4.ª de esa red, 429; desde la otra, 200
    """
    email = _correo()
    red = _red("club")

    estados = [(await _pide_reset(client, email, red)).status_code for _ in range(4)]
    otra = await _pide_reset(client, email, _red("casa"))

    assert estados == [200, 200, 200, 429]
    assert otra.status_code == 200


async def test_h2_h3_the_eleventh_reset_email_of_the_day_is_not_sent(
    client: AsyncClient, mock_external_services
):
    """
    Given: Una cuenta que ha recibido 10 correos de restablecer hoy (desde redes distintas)
    When: Se pide otro desde otra red, y uno para un correo sin cuenta
    Then: 200 con la misma respuesta en los tres casos, y no sale el 11.º correo
    """
    email = _correo()
    await _registra(client, email)
    respuestas = [(await _pide_reset(client, email, _red(f"red{i}"))) for i in range(10)]
    enviados = [
        c
        for c in mock_external_services.send_password_reset_email.await_args_list
        if c.kwargs["to_email"] == email
    ]
    assert len(enviados) == 10

    undecima = await _pide_reset(client, email, _red("red11"))
    sin_cuenta = await _pide_reset(client, _correo(), _red("red12"))

    assert undecima.status_code == 200
    assert (
        sum(
            1
            for c in mock_external_services.send_password_reset_email.await_args_list
            if c.kwargs["to_email"] == email
        )
        == 10
    )
    normal = {**respuestas[0].json(), "email": None}
    assert {**undecima.json(), "email": None} == normal
    assert {**sin_cuenta.json(), "email": None} == normal


async def test_m2_signing_in_resets_the_daily_reset_quota(
    client: AsyncClient, mock_external_services
):
    """
    Given: Una cuenta que gastó sus 10 correos de restablecer del día
    When: Inicia sesión con su contraseña y vuelve a pedir el enlace
    Then: Sale el correo: iniciar sesión pone el cupo a cero (M-2)
    """
    email = _correo()
    await _registra(client, email, CLAVE_DEL_DUENO, "Ana")
    for i in range(10):
        await _pide_reset(client, email, _red(f"red{i}"))
    await _pide_reset(client, email, _red("red10"))

    def enviados() -> int:
        return sum(
            1
            for c in mock_external_services.send_password_reset_email.await_args_list
            if c.kwargs["to_email"] == email
        )

    assert enviados() == 10
    entra = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": CLAVE_DEL_DUENO},
        headers=_red("login"),
    )
    assert entra.status_code == 200, entra.text
    client.cookies.clear()

    await _pide_reset(client, email, _red("red11"))

    assert enviados() == 11
