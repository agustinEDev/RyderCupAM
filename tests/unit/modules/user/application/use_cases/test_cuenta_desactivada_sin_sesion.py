"""
Una cuenta desactivada se queda sin sesión al momento (BE #744).

Antes, desactivar solo cambiaba `is_active`: el token de acceso seguía valiendo y el
refresco seguía dando tokens hasta 7 días. Un administrador desactivado seguía
pasando las rutas de administración.

  #   caso                                            | esperado
  ----|------------------------------------------------|---------------------------------
  S1  se desactiva una cuenta con 2 dispositivos      | todos sus dispositivos y tokens,
                                                      |   revocados en la misma transacción
  S2  la desactivación                                | queda en el log de seguridad: quién,
                                                      |   a quién y cuánto se revocó
  S3  su siguiente petición (get_current_user)        | sin usuario: 401
  S4  su refresco                                     | rechazado, motivo USER_INACTIVE
  S5  se reactiva                                     | las sesiones viejas no vuelven
  S6  falla el log de seguridad                       | la desactivación responde bien igual
  S7  activar una cuenta que ya está activa           | sus sesiones siguen: no se revoca nada
  S8  el refresco de una desactivada                  | revoca ese token (no vale al reactivar)
  S9  reactivar                                       | revoca cualquier sesión que se colara
                                                      |   (un login a la vez que la desactivación)
  S10 el refresco de una desactivada, ya revocado     | el motivo es USER_INACTIVE, no REVOKED
  S11 el rechazo del refresco                         | lleva el usuario (para el log)
  S12 desactivar y reactivar, desde una IP y navegador| los dos quedan en el log con ellos
"""

from unittest.mock import Mock

import pytest

from src.modules.user.application.dto.user_dto import RefreshAccessTokenRequestDTO
from src.modules.user.application.use_cases.admin_set_user_active_use_case import (
    AdminSetUserActiveUseCase,
)
from src.modules.user.application.use_cases.get_current_user_use_case import (
    GetCurrentUserUseCase,
)
from src.modules.user.application.use_cases.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
    RefreshRejectedError,
    RefreshRejection,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.infrastructure.security.security_audit_logger import SecurityAuditLogger
from src.shared.infrastructure.security.jwt_handler import JWTTokenService

pytestmark = pytest.mark.asyncio

ADMIN = "5f0c8a2e-1b3d-4e6f-9a7b-2c4d6e8f0a1b"
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 Version/18.1 Mobile/15E148 Safari/604.1"
MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.1 Safari/605.1.15"


async def _escena():
    uow = InMemoryUnitOfWork()
    ana = User.create(
        first_name="Ana",
        last_name="Baja",
        email_str="ana.baja@example.com",
        plain_password="V@l1dP@ss123!",
    )
    tokens = JWTTokenService()
    dispositivos, jwts = [], []
    async with uow:
        await uow.users.save(ana)
        for ua, ip in ((IPHONE, "203.0.113.7"), (MAC, "198.51.100.9")):
            d = UserDevice.create(user_id=ana.id, fingerprint=DeviceFingerprint.create(ua, ip))
            await uow.user_devices.save(d)
            jwt = tokens.create_refresh_token(data={"sub": str(ana.id.value)})
            await uow.refresh_tokens.save(
                RefreshToken.create(user_id=ana.id, token=jwt, device_id=d.id, expires_in_days=7)
            )
            dispositivos.append(d)
            jwts.append(jwt)
    auditoria = Mock()
    return uow, ana, dispositivos, jwts, auditoria, AdminSetUserActiveUseCase(uow, auditoria)


async def test_s1_desactivar_revoca_todos_sus_dispositivos_y_tokens():
    """
    Given: Ana con 2 dispositivos y su sesión en cada uno
    When: Un administrador la desactiva
    Then: Ningún dispositivo activo ni token sin revocar
    """
    uow, ana, _dispositivos, _jwts, _auditoria, caso = await _escena()

    await caso.execute(str(ana.id.value), is_active=False, actor_user_id=ADMIN)

    async with uow:
        assert await uow.user_devices.find_active_by_user(ana.id) == []
        assert all(t.revoked for t in await uow.refresh_tokens.find_all_by_user(ana.id))


async def test_s2_la_desactivacion_queda_en_el_log_de_seguridad():
    """
    Given: Ana con 2 dispositivos
    When: Un administrador la desactiva
    Then: El log recibe quién, a quién, y 2 dispositivos y 2 sesiones revocadas
    """
    _uow, ana, _d, _j, auditoria, caso = await _escena()

    await caso.execute(str(ana.id.value), is_active=False, actor_user_id=ADMIN)

    auditoria.log_account_deactivated.assert_called_once_with(
        user_id=ADMIN,
        deactivated_user_id=str(ana.id.value),
        devices_revoked=2,
        tokens_revoked=2,
        ip_address="unknown",
        user_agent="unknown",
    )


async def test_s3_su_siguiente_peticion_no_tiene_usuario():
    """
    Given: Ana desactivada
    When: Llega una petición con su token de acceso, que aún no ha caducado
    Then: get_current_user no la encuentra: 401, sin esperar a que caduque
    """
    uow, ana, _d, _j, _a, caso = await _escena()
    await caso.execute(str(ana.id.value), is_active=False, actor_user_id=ADMIN)

    assert await GetCurrentUserUseCase(uow).execute(str(ana.id.value)) is None


async def test_s4_su_refresco_se_rechaza_por_cuenta_desactivada():
    """
    Given: Ana desactivada, con un token de refresco que se colara (sin revocar)
    When: Refresca
    Then: Rechazado con USER_INACTIVE
    """
    uow, ana, _d, jwts, _a, _caso = await _escena()
    ana.deactivate(deactivated_by_user_id=ADMIN)
    async with uow:
        await uow.users.save(ana)
    refresco = RefreshAccessTokenUseCase(
        uow, JWTTokenService(), security_audit=SecurityAuditLogger()
    )

    with pytest.raises(RefreshRejectedError) as rechazo:
        await refresco.execute(RefreshAccessTokenRequestDTO(user_agent=IPHONE), jwts[0])
    assert rechazo.value.motivo is RefreshRejection.USER_INACTIVE


async def test_s5_reactivar_no_devuelve_las_sesiones():
    """
    Given: Ana desactivada (sesiones revocadas)
    When: Un administrador la reactiva
    Then: Sus tokens siguen revocados: tiene que entrar otra vez
    """
    uow, ana, _d, _j, _a, caso = await _escena()
    await caso.execute(str(ana.id.value), is_active=False, actor_user_id=ADMIN)

    await caso.execute(str(ana.id.value), is_active=True, actor_user_id=ADMIN)

    async with uow:
        assert all(t.revoked for t in await uow.refresh_tokens.find_all_by_user(ana.id))
        assert await uow.user_devices.find_active_by_user(ana.id) == []


async def test_s6_un_fallo_del_log_no_deshace_la_desactivacion(caplog):
    """
    Given: Ana, y el log de seguridad que falla
    When: Un administrador la desactiva
    Then: Queda desactivada y sin sesiones; el fallo, en el log con su tipo
    """
    uow, ana, _d, _j, auditoria, caso = await _escena()
    auditoria.log_account_deactivated.side_effect = RuntimeError("disco lleno: secreto")

    with caplog.at_level("ERROR"):
        await caso.execute(str(ana.id.value), is_active=False, actor_user_id=ADMIN)

    async with uow:
        assert not (await uow.users.find_by_id(ana.id)).is_active
    assert "RuntimeError" in caplog.text and "secreto" not in caplog.text


async def test_s7_activar_una_cuenta_activa_no_le_quita_la_sesion():
    """
    Given: Ana activa, con 2 sesiones
    When: Un administrador la marca como activa (otra vez)
    Then: Sus dispositivos y tokens siguen activos, y no hay nada en el log
    """
    uow, ana, _d, _j, auditoria, caso = await _escena()

    await caso.execute(str(ana.id.value), is_active=True, actor_user_id=ADMIN)

    async with uow:
        assert len(await uow.user_devices.find_active_by_user(ana.id)) == 2
        assert not any(t.revoked for t in await uow.refresh_tokens.find_all_by_user(ana.id))
    auditoria.log_account_deactivated.assert_not_called()


async def test_s8_el_refresco_de_una_desactivada_revoca_ese_token():
    """
    Given: Ana desactivada, con un token de refresco que se coló sin revocar
    When: Refresca
    Then: Rechazado, y ese token queda revocado: no volverá a valer al reactivarla
    """
    uow, ana, _d, jwts, _a, _caso = await _escena()
    ana.deactivate(deactivated_by_user_id=ADMIN)
    async with uow:
        await uow.users.save(ana)

    with pytest.raises(RefreshRejectedError):
        await RefreshAccessTokenUseCase(
            uow, JWTTokenService(), security_audit=SecurityAuditLogger()
        ).execute(RefreshAccessTokenRequestDTO(user_agent=IPHONE), jwts[0])

    async with uow:
        assert (await uow.refresh_tokens.find_by_token_hash(jwts[0])).revoked


async def test_s9_reactivar_revoca_lo_que_se_colara():
    """
    Given: Ana desactivada, y un token suyo sin revocar (un login a la vez que la
           desactivación)
    When: Un administrador la reactiva
    Then: Ese token queda revocado: reactivar no devuelve ninguna sesión
    """
    uow, ana, _d, _jwts, _a, caso = await _escena()
    ana.deactivate(deactivated_by_user_id=ADMIN)
    async with uow:
        await uow.users.save(ana)

    await caso.execute(str(ana.id.value), is_active=True, actor_user_id=ADMIN)

    async with uow:
        assert all(t.revoked for t in await uow.refresh_tokens.find_all_by_user(ana.id))
        # Y el dispositivo que dio de alta ese login, también (revisores)
        assert await uow.user_devices.find_active_by_user(ana.id) == []


async def test_s10_con_el_token_ya_revocado_el_motivo_es_la_cuenta_desactivada():
    """
    Given: Ana desactivada por un administrador (sus tokens, revocados)
    When: Refresca
    Then: El motivo es USER_INACTIVE: el log dirá «desactivada», no «revocado»
    """
    uow, ana, _d, jwts, _a, caso = await _escena()
    await caso.execute(str(ana.id.value), is_active=False, actor_user_id=ADMIN)

    with pytest.raises(RefreshRejectedError) as rechazo:
        await RefreshAccessTokenUseCase(
            uow, JWTTokenService(), security_audit=SecurityAuditLogger()
        ).execute(RefreshAccessTokenRequestDTO(user_agent=IPHONE), jwts[0])
    assert rechazo.value.motivo is RefreshRejection.USER_INACTIVE


async def test_s11_el_rechazo_lleva_el_usuario_para_el_log():
    """
    Given: Ana desactivada
    When: Refresca
    Then: El rechazo lleva su id (va al log de seguridad, nunca al cliente)
    """
    uow, ana, _d, jwts, _a, caso = await _escena()
    await caso.execute(str(ana.id.value), is_active=False, actor_user_id=ADMIN)

    with pytest.raises(RefreshRejectedError) as rechazo:
        await RefreshAccessTokenUseCase(
            uow, JWTTokenService(), security_audit=SecurityAuditLogger()
        ).execute(RefreshAccessTokenRequestDTO(user_agent=IPHONE), jwts[0])
    assert rechazo.value.user_id == str(ana.id.value)


async def test_s12_desactivar_y_reactivar_quedan_en_el_log_con_ip_y_navegador():
    """
    Given: Ana, y un administrador con su IP y su navegador
    When: La desactiva y la reactiva
    Then: Los dos cambios quedan en el log de seguridad, con su IP y su navegador
    """
    _uow, ana, _d, _j, auditoria, caso = await _escena()

    await caso.execute(
        str(ana.id.value),
        is_active=False,
        actor_user_id=ADMIN,
        ip_address="203.0.113.9",
        user_agent="Admin UA",
    )
    await caso.execute(
        str(ana.id.value),
        is_active=True,
        actor_user_id=ADMIN,
        ip_address="203.0.113.9",
        user_agent="Admin UA",
    )

    baja = auditoria.log_account_deactivated.call_args.kwargs
    alta = auditoria.log_account_reactivated.call_args.kwargs
    assert (baja["ip_address"], baja["user_agent"]) == ("203.0.113.9", "Admin UA")
    assert (alta["user_id"], alta["reactivated_user_id"]) == (ADMIN, str(ana.id.value))
    assert (alta["ip_address"], alta["user_agent"]) == ("203.0.113.9", "Admin UA")
