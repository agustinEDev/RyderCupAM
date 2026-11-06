"""
El correo de «intentos fallidos» al dueño de la cuenta (BE #732).

  #   caso                                                 | ¿correo?
  ----|-----------------------------------------------------|--------------------------------
  A1  una red queda bloqueada para su cuenta, desde España  | sí: motivo «red», el país en
                                                            |   castellano y la hora de España
  A2  salta el respaldo                                     | sí: motivo «respaldo»
  A3  ya avisó hace menos de una hora                       | no: uno por hora y cuenta
  A3b avisó hace más de una hora                            | sí
  A4  su correo aún no está confirmado                      | no
  A5  falla el envío                                        | no lanza, y no cuenta para el tope
  A6  tras avisar                                           | la cuenta queda apuntada
  A7  sin país                                              | el correo no lo menciona
  A8  la cuenta ya no existe                                | no
  A9  el tope global de avisos (20/hora) está lleno          | no, y no queda apuntado
  A11 falla el guardado de la reserva                        | el hueco del tope vuelve
  A11b falla al confirmar la reserva (commit)                | el hueco del tope vuelve también
  A10 la reserva se hace con la fila bloqueada, ANTES de     | dos a la vez no mandan dos
      enviar                                                 |   (la prueba de verdad, en
                                                             |   integración)
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.modules.user.application.dto.user_dto import AvisoDeFallosRequestDTO
from src.modules.user.application.services.aviso_de_fallos_de_login import AvisoDeFallosDeLogin
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.shared.domain.entities.country import Country
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = pytest.mark.asyncio

# 6 nov 2026, 9:30 UTC = 10:30 en la península
AHORA = datetime(2026, 11, 6, 9, 30)


class _Paises:
    async def find_by_code(self, code: CountryCode):
        if code.value == "ES":
            return Country(code=CountryCode("ES"), name_en="Spain", name_es="España")
        return None


class _Cupo:
    def __init__(self, libre=True):
        self.libre = libre
        self.pedidos = 0

    def reserva(self, motivo: str) -> bool:
        self.pedidos += 1
        self.motivo = motivo
        return self.libre

    def devuelve(self, motivo: str) -> None:
        self.devueltos = getattr(self, "devueltos", 0) + 1


async def _escena(avisado_hace=None, enviado=True, cupo=None):
    uow = InMemoryUnitOfWork()
    ana = User.create(
        first_name="Ana",
        last_name="Red",
        email_str="ana@example.com",
        plain_password="V@l1dP@ss123!",
    )
    ana.verify_email_from_oauth()
    if avisado_hace is not None:
        ana.apunta_el_aviso_de_fallos(AHORA - avisado_hace)
    async with uow:
        await uow.users.save(ana)
    correo = AsyncMock()
    correo.send_failed_logins_notification = AsyncMock(return_value=enviado)
    return (
        uow,
        ana,
        correo,
        AvisoDeFallosDeLogin(uow, correo, _Paises(), cupo or _Cupo(), reloj=lambda: AHORA),
    )


def _pide(ana, motivo="red", pais="ES", verificado=True):
    return AvisoDeFallosRequestDTO(
        user_id=str(ana.id.value),
        email="ana@example.com",
        nombre="Ana",
        verificado=verificado,
        country_code=pais,
        motivo=motivo,
    )


async def test_a1_una_red_bloqueada_avisa_con_el_pais_y_la_hora_de_espana():
    """
    Given: Ana, con el correo confirmado y sin avisos
    When: Una red de España queda bloqueada para su cuenta
    Then: Le llega el correo: motivo «red», «España» y las 10:30 (hora de España)
    """
    _uow, ana, correo, aviso = await _escena()

    await aviso.avisa(_pide(ana))

    kw = correo.send_failed_logins_notification.await_args.kwargs
    assert kw["to_email"] == "ana@example.com" and kw["user_name"] == "Ana"
    assert kw["motivo"] == "red" and kw["pais"] == "España"
    assert kw["cuando"] == "6 nov 2026, 10:30 (hora de España)"
    assert (kw["fallos"], kw["minutos"]) == (10, 30)


async def test_a2_salta_el_respaldo_y_avisa_con_su_motivo():
    """
    Given: Ana sin avisos
    When: Salta el respaldo de su cuenta
    Then: El correo va con motivo «respaldo»
    """
    _uow, ana, correo, aviso = await _escena()

    await aviso.avisa(_pide(ana, motivo="respaldo"))

    assert correo.send_failed_logins_notification.await_args.kwargs["motivo"] == "respaldo"
    kw = correo.send_failed_logins_notification.await_args.kwargs
    assert (kw["fallos"], kw["minutos"]) == (50, 30)


async def test_a3_uno_por_hora_y_cuenta():
    """
    Given: Ana, avisada hace 20 minutos
    When: Se bloquea otra red
    Then: No hay correo
    """
    _uow, ana, correo, aviso = await _escena(avisado_hace=timedelta(minutes=20))

    await aviso.avisa(_pide(ana))

    correo.send_failed_logins_notification.assert_not_awaited()


async def test_a3b_pasada_la_hora_vuelve_a_avisar():
    """
    Given: Ana, avisada hace una hora y un minuto
    When: Se bloquea otra red
    Then: Le llega el correo
    """
    _uow, ana, correo, aviso = await _escena(avisado_hace=timedelta(hours=1, minutes=1))

    await aviso.avisa(_pide(ana))

    correo.send_failed_logins_notification.assert_awaited_once()


async def test_a4_nunca_a_un_correo_sin_confirmar():
    """
    Given: Ana con el correo sin confirmar
    When: Se bloquea una red
    Then: No hay correo
    """
    _uow, ana, correo, aviso = await _escena()

    await aviso.avisa(_pide(ana, verificado=False))

    correo.send_failed_logins_notification.assert_not_awaited()


async def test_a5_un_fallo_del_envio_no_lanza_ni_cuenta(caplog):
    """
    Given: El proveedor de correo falla (con la dirección en su mensaje)
    When: Se avisa
    Then: No lanza; no queda apuntado; el log lleva el tipo, no el mensaje
    """
    uow, ana, correo, aviso = await _escena()
    correo.send_failed_logins_notification.side_effect = RuntimeError("ana@example.com rechazada")

    await aviso.avisa(_pide(ana))

    async with uow:
        assert (await uow.users.find_by_id(ana.id)).failed_login_notice_at is None
    assert "RuntimeError" in caplog.text and "ana@example.com" not in caplog.text


async def test_a5b_un_envio_que_no_sale_no_cuenta():
    """
    Given: El proveedor devuelve que no se envió
    When: Se avisa
    Then: No queda apuntado: el siguiente bloqueo podrá avisar
    """
    uow, ana, _correo, aviso = await _escena(enviado=False)

    await aviso.avisa(_pide(ana))

    async with uow:
        assert (await uow.users.find_by_id(ana.id)).failed_login_notice_at is None


async def test_a6_tras_avisar_la_cuenta_queda_apuntada():
    """
    Given: Ana sin avisos
    When: Se le avisa
    Then: Queda apuntada la hora del aviso
    """
    uow, ana, _correo, aviso = await _escena()

    await aviso.avisa(_pide(ana))

    async with uow:
        assert (await uow.users.find_by_id(ana.id)).failed_login_notice_at == AHORA


async def test_a7_sin_pais_el_correo_no_lo_menciona():
    """
    Given: Una red sin país (sin Cloudflare)
    When: Se avisa
    Then: El correo va sin país
    """
    _uow, ana, correo, aviso = await _escena()

    await aviso.avisa(_pide(ana, pais=None))

    assert correo.send_failed_logins_notification.await_args.kwargs["pais"] is None


async def test_a8_una_cuenta_que_ya_no_existe_no_recibe_nada():
    """
    Given: Un aviso de una cuenta que se borró entre medias
    When: Se avisa
    Then: No hay correo ni error
    """
    _uow, _ana, correo, aviso = await _escena()
    otro = User.create(
        first_name="X", last_name="Y", email_str="x@example.com", plain_password="V@l1dP@ss123!"
    )

    await aviso.avisa(_pide(otro))

    correo.send_failed_logins_notification.assert_not_awaited()


async def test_a9_con_el_tope_global_lleno_no_se_envia_ni_se_apunta():
    """
    Given: El tope global de avisos de fallos de esta hora, lleno
    When: Se bloquea una red para Ana
    Then: No hay correo, y Ana no queda apuntada: el siguiente podrá avisar
    """
    uow, ana, correo, aviso = await _escena(cupo=_Cupo(libre=False))

    await aviso.avisa(_pide(ana))

    correo.send_failed_logins_notification.assert_not_awaited()
    async with uow:
        assert (await uow.users.find_by_id(ana.id)).failed_login_notice_at is None


async def test_a9b_el_tope_no_se_gasta_si_ya_aviso_en_la_hora():
    """
    Given: Ana avisada hace 20 minutos
    When: Se bloquea otra red
    Then: No se pide hueco en el tope global: no hay nada que enviar
    """
    cupo = _Cupo()
    _uow, ana, _correo, aviso = await _escena(avisado_hace=timedelta(minutes=20), cupo=cupo)

    await aviso.avisa(_pide(ana))

    assert cupo.pedidos == 0


async def test_a10_reserva_con_la_fila_bloqueada_antes_de_enviar():
    """
    Given: Ana sin avisos
    When: Se avisa
    Then: Se relee con la fila bloqueada, y queda apuntada ANTES del envío
    """
    uow, ana, correo, aviso = await _escena()
    orden = []
    original = uow.users.find_by_id_for_update

    async def bloqueada(user_id):
        orden.append("bloqueo")
        return await original(user_id)

    async def envia(**_kw):
        async with uow:
            apuntada = (await uow.users.find_by_id(ana.id)).failed_login_notice_at
        orden.append(("envío", apuntada))
        return True

    uow.users.find_by_id_for_update = bloqueada
    correo.send_failed_logins_notification = envia

    await aviso.avisa(_pide(ana))

    assert orden == ["bloqueo", ("envío", AHORA)]


async def test_a11_si_falla_el_guardado_de_la_reserva_el_hueco_vuelve():
    """
    Given: Ana sin avisos, y la BD que falla al guardar la reserva
    When: Se avisa
    Then: No hay correo, y el hueco del tope global se devuelve
    """
    cupo = _Cupo()
    uow, _ana, correo, aviso = await _escena(cupo=cupo)

    async def roto(_user):
        raise RuntimeError("la BD no responde")

    uow.users.save = roto

    await aviso.avisa(_pide(_ana))

    correo.send_failed_logins_notification.assert_not_awaited()
    assert getattr(cupo, "devueltos", 0) == 1


async def test_a11b_si_falla_al_confirmar_la_reserva_el_hueco_vuelve():
    """
    Given: Ana sin avisos, y la BD que falla al confirmar (commit), no al guardar
    When: Se avisa
    Then: No hay correo, y el hueco del tope global se devuelve (CodeRabbit)
    """
    cupo = _Cupo()
    uow, ana, correo, aviso = await _escena(cupo=cupo)

    async def commit_roto():
        raise RuntimeError("la BD no confirma")

    uow.commit = commit_roto

    await aviso.avisa(_pide(ana))

    correo.send_failed_logins_notification.assert_not_awaited()
    assert getattr(cupo, "devueltos", 0) == 1
