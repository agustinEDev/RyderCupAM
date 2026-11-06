"""
El login se frena por correo y red, y el dueño no se queda fuera (BE #732, ADR-043).

Por la API, con la red de cada intento simulada con X-Test-Client-ID (fuera de
producción es la clave de red de los límites). Los números de la tabla aprobada:
5 intentos por minuto y 10 fallos (30 min de bloqueo) por correo + red; el respaldo
de la cuenta, 50 fallos en una hora desde cualquier red, solo para desconocidos.

  #    caso                                                  | esperado
  -----|----------------------------------------------------|------------------------------
  I1   10 fallos desde la red A                              | 9 x 401 y el 10º 423 «Account
                                                             |   locked until …»
  I2   con A bloqueada, el dueño desde B                     | 200
  I3   con A bloqueada, su dispositivo (cookie) desde A      | 200
  I4   con A bloqueada, la buena desde A sin cookie          | 423
  I5   5 intentos en un minuto desde A                       | el 6º 429 en A; B entra
  I6   con A bloqueada para Ana, otra cuenta desde A         | 200
  I7   respaldo saltado: desconocido / su dispositivo        | 423 / 200
  I8   un correo que no existe                               | el mismo 401 y 423
  I9   acertar desde A                                       | A vuelve a cero: 9 fallos más, 401
  I10  una red se bloquea, con el correo confirmado          | llega el correo de intentos fallidos
  I10b con el correo sin confirmar                           | no llega
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from main import app as fastapi_app
from src.config.aviso_en_segundo_plano import espera_los_avisos_pendientes
from src.config.dependencies import get_db_session
from src.config.rate_limit import limiter

pytestmark = pytest.mark.asyncio

CLAVE = "ValidPassword123!"
MALA = "WrongPassword123!"


@pytest.fixture
def sin_cupo_por_minuto():
    """Para llegar a 10 fallos desde una red sin chocar con los 5 por minuto (I5 lo prueba)."""
    previous = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = previous


async def _sql(sentencia: str, **parametros):
    override = fastapi_app.dependency_overrides[get_db_session]
    async for sesion in override():
        resultado = await sesion.execute(text(sentencia), parametros)
        await sesion.commit()
        return resultado
    return None


async def _registra(client: AsyncClient, prefijo: str, verificado: bool = False) -> str:
    email = f"{prefijo}-{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": CLAVE,
            "first_name": "Ana",
            "last_name": "Red",
            "accept_terms": True,
        },
        headers={"X-Test-Client-ID": f"alta-{uuid.uuid4().hex[:6]}"},
    )
    assert r.status_code == 201, r.text
    if verificado:
        await _sql("update users set email_verified = true where email = :e", e=email)
    client.cookies.clear()
    return email


async def _login(client: AsyncClient, email: str, red: str, clave: str = CLAVE, cookie=None):
    client.cookies.clear()
    if cookie:
        client.cookies.set("device_id", cookie)
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": clave},
        headers={"X-Test-Client-ID": red},
    )
    client.cookies.clear()
    return r


async def _falla(client: AsyncClient, email: str, red: str, veces: int) -> list[int]:
    return [(await _login(client, email, red, MALA)).status_code for _ in range(veces)]


async def _dispositivo(client: AsyncClient, email: str, red: str) -> str:
    """Entra con la buena y devuelve el id del dispositivo de su cookie."""
    client.cookies.clear()
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": CLAVE},
        headers={"X-Test-Client-ID": red},
    )
    assert r.status_code == 200, r.text
    device_id = r.json()["device_id"]
    client.cookies.clear()
    return device_id


async def test_i1_diez_fallos_desde_una_red_la_bloquean(client, sin_cupo_por_minuto):
    """
    Given: Ana
    When: Alguien falla su contraseña 10 veces desde la red A
    Then: 9 x 401 y el 10º 423, con «Account locked until …»
    """
    ana = await _registra(client, "i1")
    red_a = f"a-{uuid.uuid4().hex[:6]}"

    codigos = await _falla(client, ana, red_a, 10)

    assert codigos == [401] * 9 + [423]
    r = await _login(client, ana, red_a, MALA)
    assert r.status_code == 423
    assert "Account locked" in r.json()["detail"] and "until" in r.json()["detail"]


async def test_i2_i3_i4_con_a_bloqueada_el_dueno_entra_desde_b_o_con_su_dispositivo(
    client, sin_cupo_por_minuto
):
    """
    Given: Ana con un dispositivo suyo, y la red A bloqueada para ella
    When: Entra desde B; desde A con su dispositivo; y desde A sin cookie
    Then: 200, 200 y 423
    """
    ana = await _registra(client, "i2")
    red_a, red_b = f"a-{uuid.uuid4().hex[:6]}", f"b-{uuid.uuid4().hex[:6]}"
    movil = await _dispositivo(client, ana, red_b)
    await _falla(client, ana, red_a, 10)

    assert (await _login(client, ana, red_b)).status_code == 200
    assert (await _login(client, ana, red_a, cookie=movil)).status_code == 200
    assert (await _login(client, ana, red_a)).status_code == 423


async def test_i5_el_sexto_intento_en_un_minuto_da_429_solo_en_esa_red(client):
    """
    Given: 5 intentos con el correo de Ana desde A en un minuto
    When: Llega el sexto desde A, y uno desde B
    Then: 429 en A; 200 desde B (antes, 429 para todos)
    """
    ana = await _registra(client, "i5")
    red_a, red_b = f"a-{uuid.uuid4().hex[:6]}", f"b-{uuid.uuid4().hex[:6]}"
    await _falla(client, ana, red_a, 5)

    assert (await _login(client, ana, red_a)).status_code == 429
    assert (await _login(client, ana, red_b)).status_code == 200


async def test_i6_el_bloqueo_es_de_la_pareja_correo_y_red(client, sin_cupo_por_minuto):
    """
    Given: La red A bloqueada para Ana
    When: Luis entra desde A
    Then: 200
    """
    ana = await _registra(client, "i6a")
    luis = await _registra(client, "i6l")
    red_a = f"a-{uuid.uuid4().hex[:6]}"
    await _falla(client, ana, red_a, 10)

    assert (await _login(client, luis, red_a)).status_code == 200


async def test_i7_el_respaldo_frena_a_los_desconocidos_y_no_al_dispositivo_del_dueno(
    client, sin_cupo_por_minuto
):
    """
    Given: Ana con su dispositivo, y 50 fallos desde 10 redes distintas
    When: Entra un desconocido desde otra red, y Ana con su dispositivo
    Then: 423 al desconocido, 200 a Ana
    """
    ana = await _registra(client, "i7")
    movil = await _dispositivo(client, ana, f"casa-{uuid.uuid4().hex[:6]}")
    for i in range(10):
        await _falla(client, ana, f"bot{i}-{uuid.uuid4().hex[:6]}", 5)

    assert (await _login(client, ana, f"nueva-{uuid.uuid4().hex[:6]}")).status_code == 423
    assert (
        await _login(client, ana, f"otra-{uuid.uuid4().hex[:6]}", cookie=movil)
    ).status_code == 200


async def test_i8_un_correo_que_no_existe_responde_igual(client, sin_cupo_por_minuto):
    """
    Given: Un correo que no existe
    When: Falla 10 veces desde A
    Then: 9 x 401 y el 10º 423, como uno que existe (sin enumeración, BE #281)
    """
    nadie = f"nadie-{uuid.uuid4().hex[:8]}@example.com"

    assert await _falla(client, nadie, f"a-{uuid.uuid4().hex[:6]}", 10) == [401] * 9 + [423]


async def test_i9_acertar_pone_a_cero_esa_red(client, sin_cupo_por_minuto):
    """
    Given: 9 fallos de Ana desde A
    When: Acierta desde A, y luego falla 9 veces más desde A
    Then: 200, y los 9 siguientes son 401: A había vuelto a cero
    """
    ana = await _registra(client, "i9")
    red_a = f"a-{uuid.uuid4().hex[:6]}"
    await _falla(client, ana, red_a, 9)

    assert (await _login(client, ana, red_a)).status_code == 200
    assert await _falla(client, ana, red_a, 9) == [401] * 9


async def test_i10_avisa_al_dueno_si_su_correo_esta_confirmado(
    client, sin_cupo_por_minuto, mock_external_services
):
    """
    Given: Ana con el correo confirmado, y Luis sin confirmar
    When: Una red se bloquea para cada uno
    Then: A Ana le llega el correo de intentos fallidos; a Luis, no
    """
    ana = await _registra(client, "i10a", verificado=True)
    luis = await _registra(client, "i10l")
    aviso = mock_external_services.send_failed_logins_notification
    aviso.reset_mock()

    await _falla(client, ana, f"a-{uuid.uuid4().hex[:6]}", 10)
    await _falla(client, luis, f"a-{uuid.uuid4().hex[:6]}", 10)
    await espera_los_avisos_pendientes()

    destinos = [c.kwargs["to_email"] for c in aviso.await_args_list]
    assert destinos == [ana]
    assert aviso.await_args.kwargs["motivo"] == "red"
