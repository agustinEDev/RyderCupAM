"""
El login se frena por correo y origen, y el dispositivo fiable no se bloquea (BE #732).

Antes, 5 intentos por minuto con tu correo desde cualquier red te dejaban en 429, y
10 contraseñas malas bloqueaban tu cuenta 30 minutos para todo el mundo. Ahora cada
pareja correo + red lleva lo suyo; un dispositivo activo de la cuenta que trae su
cookie cuenta aparte; y el respaldo de la cuenta (50 en una hora, todas las redes)
solo frena a los dispositivos desconocidos. Los números de la tabla aprobada.

  #    caso                                                  | esperado
  -----|----------------------------------------------------|-----------------------------
  U1   10 fallos desde la red A                              | el 10º da 423; el dueño entra
                                                             |   desde B con la buena
  U2   con A bloqueada, la buena desde A sin cookie          | 423, sin comprobar la contraseña
  U3   con A bloqueada, el dispositivo fiable desde A        | entra (la wifi del club)
  U4   el 6º intento en un minuto desde A                    | se rechaza (429); desde B, no
  U5   con A bloqueada para Ana                              | otra cuenta entra desde A
  U6   respaldo saltado: un dispositivo desconocido          | 423 aunque traiga la buena
  U6b  respaldo saltado: el fiable                           | entra
  U6c  respaldo saltado: un desconocido                      | la contraseña no se comprueba
  U7   el fiable falla 10 veces                              | pierde el pase: cuenta como su red
  U7b  y luego trae la buena, con la red y el respaldo limpios| entra (como desconocido), no 423
  U8   cookie de otra cuenta, de un revocado o inventada     | sin pase
  U9   acertar                                               | a cero esa pareja; no las demás,
                                                             |   ni el respaldo
  U10  un correo que no existe                               | el mismo 423 y el mismo 429
  U11  cada fallo                                            | suma en el respaldo de la cuenta
  U12  una red se bloquea / salta el respaldo                | avisa al dueño con su motivo y país
  U12b un correo que no existe se bloquea                    | sin aviso
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.config.freno_del_login import FrenoDelLoginEnMemoria
from src.modules.user.application.dto.user_dto import LoginRequestDTO
from src.modules.user.application.ports.freno_del_login_port import (
    origen_de_dispositivo,
    origen_de_red,
)
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.exceptions import (
    AccountLockedException,
    LoginAttemptsExceededException,
)
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.shared.infrastructure.security.jwt_handler import JWTTokenService
from tests.unit.modules.user.application.use_cases._registro_falso import (
    registro_de_dispositivo_falso,
)

pytestmark = pytest.mark.asyncio

ANA = "ana.red@example.com"
LUIS = "luis.red@example.com"
BUENA = "V@l1dP@ss123!"
MALA = "Mala-Pass-1!"
RED_A = "203.0.113.7"
RED_B = "198.51.100.9"
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 Version/18.1 Mobile/15E148 Safari/604.1"


class Escena:
    def __init__(self):
        self.uow = InMemoryUnitOfWork()
        self.freno = FrenoDelLoginEnMemoria()
        self.aviso_de_fallos = AsyncMock()
        self.caso = LoginUserUseCase(
            self.uow,
            JWTTokenService(),
            registro_de_dispositivo_falso(),
            AsyncMock(),
            self.freno,
            self.aviso_de_fallos,
        )

    async def usuario(self, email=ANA, verificado=True) -> User:
        u = User.create(first_name="Ana", last_name="Red", email_str=email, plain_password=BUENA)
        if verificado:
            u.verify_email_from_oauth()
        async with self.uow:
            await self.uow.users.save(u)
        return u

    async def dispositivo(self, user: User, activo=True) -> str:
        d = UserDevice.create(user_id=user.id, fingerprint=DeviceFingerprint.create(IPHONE, RED_A))
        if not activo:
            d.revoke()
        async with self.uow:
            await self.uow.user_devices.save(d)
        return str(d.id.value)

    async def entra(self, email=ANA, clave=BUENA, red=RED_A, cookie=None, pais=None):
        return await self.caso.execute(
            LoginRequestDTO(
                email=email,
                password=clave,
                ip_address=red,
                red=red,
                user_agent=IPHONE,
                device_id_from_cookie=cookie,
                country_code=pais,
            )
        )

    async def falla(self, veces, **kw):
        """Falla `veces` veces y devuelve qué pasó en cada una (None o la excepción)."""
        salida = []
        for _ in range(veces):
            try:
                salida.append(await self.entra(clave=MALA, **kw))
            except AccountLockedException as e:
                salida.append(e)
            self.freno._intentos.clear()  # el cupo por minuto se prueba aparte (U4)
        return salida

    async def releido(self, user: User) -> User:
        async with self.uow:
            return await self.uow.users.find_by_id(user.id)


async def test_u1_diez_fallos_bloquean_la_red_a_y_el_dueno_entra_desde_b():
    """
    Given: Ana, y alguien que falla su contraseña desde la red A
    When: Falla 10 veces, y luego Ana entra desde B con la buena
    Then: Los 9 primeros son 401 (None), el 10º es 423; Ana entra desde B
    """
    e = Escena()
    await e.usuario()

    salida = await e.falla(10, red=RED_A)

    assert salida[:9] == [None] * 9
    assert isinstance(salida[9], AccountLockedException)
    assert (await e.entra(red=RED_B)) is not None


async def test_u2_con_a_bloqueada_la_buena_desde_a_sin_cookie_da_423_sin_comprobarla(monkeypatch):
    """
    Given: La red A bloqueada para Ana
    When: Desde A, sin cookie, llega la contraseña buena
    Then: 423, y la contraseña no se llega a comprobar (no se puede seguir probando)
    """
    e = Escena()
    await e.usuario()
    await e.falla(10, red=RED_A)
    comprobadas = []
    monkeypatch.setattr(User, "verify_password", lambda self, p: comprobadas.append(p) or True)

    with pytest.raises(AccountLockedException):
        await e.entra(red=RED_A)
    assert comprobadas == []


async def test_u3_con_a_bloqueada_el_dispositivo_fiable_desde_a_entra():
    """
    Given: La red A bloqueada para Ana (la wifi del club, con el atacante dentro)
    When: Ana entra desde A con su dispositivo, que trae su cookie
    Then: Entra
    """
    e = Escena()
    ana = await e.usuario()
    movil = await e.dispositivo(ana)
    await e.falla(10, red=RED_A)

    assert (await e.entra(red=RED_A, cookie=movil)) is not None


async def test_u4_el_sexto_intento_en_un_minuto_se_rechaza_solo_en_esa_red():
    """
    Given: 5 intentos con el correo de Ana desde A en un minuto
    When: Llega el sexto desde A, y otro desde B
    Then: El de A se rechaza por cupo; el de B entra
    """
    e = Escena()
    await e.usuario()
    for _ in range(5):
        await e.entra(clave=MALA, red=RED_A)

    with pytest.raises(LoginAttemptsExceededException):
        await e.entra(red=RED_A)
    assert (await e.entra(red=RED_B)) is not None


async def test_u5_el_bloqueo_es_de_la_pareja_y_otra_cuenta_entra_desde_a():
    """
    Given: La red A bloqueada para Ana
    When: Luis entra desde A
    Then: Entra: el bloqueo es de Ana + A, no de toda la red
    """
    e = Escena()
    await e.usuario()
    await e.usuario(email=LUIS)
    await e.falla(10, red=RED_A)

    assert (await e.entra(email=LUIS, red=RED_A)) is not None


async def _con_el_respaldo_saltado(e: Escena) -> User:
    ana = await e.usuario()
    ahora = datetime.now()
    for _ in range(50):
        ana.record_failed_login(ahora=ahora)
    async with e.uow:
        await e.uow.users.save(ana)
    return ana


async def test_u6_respaldo_saltado_un_desconocido_recibe_423_con_la_buena():
    """
    Given: El respaldo de Ana saltado (50 fallos desde muchas redes)
    When: Entra un dispositivo desconocido desde una red limpia, con la buena
    Then: 423
    """
    e = Escena()
    await _con_el_respaldo_saltado(e)

    with pytest.raises(AccountLockedException):
        await e.entra(red=RED_B)


async def test_u6b_respaldo_saltado_el_fiable_entra():
    """
    Given: El respaldo de Ana saltado
    When: Entra su dispositivo fiable
    Then: Entra
    """
    e = Escena()
    ana = await _con_el_respaldo_saltado(e)
    movil = await e.dispositivo(ana)

    assert (await e.entra(red=RED_B, cookie=movil)) is not None


async def test_u7_el_fiable_que_falla_diez_veces_pierde_el_pase():
    """
    Given: El dispositivo fiable de Ana, y el respaldo saltado
    When: Ese dispositivo falla 10 veces y luego trae la buena
    Then: Su pase queda bloqueado y cuenta como desconocido: 423 por el respaldo
    """
    e = Escena()
    ana = await e.usuario()
    movil = await e.dispositivo(ana)
    await e.falla(10, red=RED_A, cookie=movil)
    assert e.freno.bloqueado_hasta(ANA, origen_de_dispositivo(movil)) is not None
    assert e.freno.bloqueado_hasta(ANA, origen_de_red(RED_A)) is None

    releida = await e.releido(ana)
    for _ in range(50):
        releida.record_failed_login()
    async with e.uow:
        await e.uow.users.save(releida)

    with pytest.raises(AccountLockedException):
        await e.entra(red=RED_A, cookie=movil)


@pytest.mark.parametrize("cual", ["otra cuenta", "revocado", "inventado"])
async def test_u8_una_cookie_que_no_es_de_un_dispositivo_activo_suyo_no_da_pase(cual):
    """
    Given: El respaldo de Ana saltado, y una cookie que no es de un dispositivo
           activo suyo
    When: Entra con esa cookie y la buena
    Then: 423: no tiene pase
    """
    e = Escena()
    ana = await _con_el_respaldo_saltado(e)
    if cual == "otra cuenta":
        cookie = await e.dispositivo(await e.usuario(email=LUIS))
    elif cual == "revocado":
        cookie = await e.dispositivo(ana, activo=False)
    else:
        cookie = "0d9c2a1e-5b7f-4c3d-8e6a-1f2b3c4d5e6f"

    with pytest.raises(AccountLockedException):
        await e.entra(red=RED_B, cookie=cookie)


async def test_u9_acertar_pone_a_cero_esa_pareja_y_no_las_demas_ni_el_respaldo():
    """
    Given: 9 fallos de Ana desde A y 9 desde B
    When: Ana acierta desde A
    Then: A vuelve a cero; B bloquea con el siguiente; el respaldo sigue en 18
    """
    e = Escena()
    ana = await e.usuario()
    await e.falla(9, red=RED_A)
    await e.falla(9, red=RED_B)

    await e.entra(red=RED_A)

    assert (await e.falla(9, red=RED_A)) == [None] * 9
    assert isinstance((await e.falla(1, red=RED_B))[0], AccountLockedException)
    assert (await e.releido(ana)).failed_login_attempts == 28


async def test_u10_un_correo_que_no_existe_da_el_mismo_423_y_el_mismo_429():
    """
    Given: Un correo que no existe
    When: Falla 10 veces desde A, y otro correo inexistente intenta 6 en un minuto
    Then: El 10º es 423 y el 6º se rechaza por cupo, como con uno que existe
    """
    e = Escena()

    salida = await e.falla(10, email="nadie@example.com", red=RED_A)
    assert salida[:9] == [None] * 9
    assert isinstance(salida[9], AccountLockedException)

    for _ in range(5):
        await e.entra(email="otro.nadie@example.com", clave=MALA, red=RED_A)
    with pytest.raises(LoginAttemptsExceededException):
        await e.entra(email="otro.nadie@example.com", red=RED_A)


async def test_u11_cada_fallo_suma_en_el_respaldo_de_la_cuenta():
    """
    Given: Ana
    When: Falla 3 veces desde A y 4 desde B
    Then: El respaldo de la cuenta lleva 7
    """
    e = Escena()
    ana = await e.usuario()
    await e.falla(3, red=RED_A)
    await e.falla(4, red=RED_B)

    assert (await e.releido(ana)).failed_login_attempts == 7


async def test_u12_avisa_al_dueno_cuando_se_bloquea_una_red_y_cuando_salta_el_respaldo():
    """
    Given: Ana, con el correo confirmado
    When: La red A se bloquea para ella, desde España; luego salta el respaldo
    Then: Un aviso con motivo «red» y su país, y otro con motivo «respaldo»
    """
    e = Escena()
    ana = await e.usuario()
    await e.falla(10, red=RED_A, pais="ES")

    primero = e.aviso_de_fallos.avisa.await_args_list[-1].args[0]
    assert (primero.motivo, primero.country_code, primero.email) == ("red", "ES", ANA)
    assert primero.user_id == str(ana.id.value) and primero.verificado

    releida = await e.releido(ana)
    releida._failed_login_attempts = 49
    releida._failed_login_window_started_at = datetime.now() - timedelta(minutes=5)
    async with e.uow:
        await e.uow.users.save(releida)
    await e.falla(1, red=RED_B)

    assert e.aviso_de_fallos.avisa.await_args_list[-1].args[0].motivo == "respaldo"
    assert e.aviso_de_fallos.avisa.await_count == 2


async def test_u12b_un_correo_que_no_existe_no_avisa_a_nadie():
    """
    Given: Un correo que no existe
    When: Su red se bloquea
    Then: No hay aviso
    """
    e = Escena()
    await e.falla(10, email="nadie@example.com", red=RED_A)

    e.aviso_de_fallos.avisa.assert_not_awaited()


async def test_u6c_con_el_respaldo_saltado_la_contrasena_de_un_desconocido_no_se_comprueba(
    monkeypatch,
):
    """
    Given: El respaldo de Ana saltado
    When: Un dispositivo desconocido trae una contraseña
    Then: 423 sin llegar a comprobarla: no se puede seguir probando
    """
    e = Escena()
    await _con_el_respaldo_saltado(e)
    comprobadas = []
    monkeypatch.setattr(User, "verify_password", lambda self, p: comprobadas.append(p) or True)

    with pytest.raises(AccountLockedException):
        await e.entra(red=RED_B)
    assert comprobadas == []


async def test_u7b_el_fiable_sin_pase_entra_como_desconocido_si_su_red_esta_limpia():
    """
    Given: El dispositivo fiable de Ana perdió el pase (10 fallos suyos)
    When: Trae la buena desde una red limpia, con el respaldo limpio
    Then: Entra: cuenta como esa red, no queda bloqueado por su pase
    """
    e = Escena()
    ana = await e.usuario()
    movil = await e.dispositivo(ana)
    await e.falla(10, red=RED_A, cookie=movil)

    assert (await e.entra(red=RED_B, cookie=movil)) is not None
