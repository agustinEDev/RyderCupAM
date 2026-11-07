"""
La regla única de los caminos que dan acceso o cambian credenciales (#749, tabla):
en una transacción, bloquear la fila de la cuenta ANTES de decidir, volver a comprobar
sobre la fila bloqueada, y escribir. Sin ella, otra operación a la vez se pisaba.

  #   Camino                                   | Si a la vez cambió la cuenta...
  ----|------------------------------------------|-------------------------------------
  A2  Google ya vinculado                      | le quitaron ese Google: sin sesión
  A3  Google                                   | la desactivaron: 403, sin sesión
  A4  abrir sesión al verificar el correo      | la desactivaron: sin sesión
  B1  Seguridad (contraseña, correo)           | se comprueba sobre la fila bloqueada
  B2  restablecer una cuenta verificada        | cierra sesiones Y dispositivos
  B3  la toma por Google                       | bloquea también si está verificada
  B5  desvincular Google                       | sobre la fila bloqueada
  B7  el administrador cambia el correo        | los enlaces de antes ya no valen
"""

import copy
from unittest.mock import AsyncMock

import pytest

from src.modules.user.application.dto.device_dto import (
    RegisterDeviceResponseDTO,
)
from src.modules.user.application.dto.oauth_dto import GoogleLoginRequestDTO
from src.modules.user.application.dto.user_dto import ResetPasswordRequestDTO
from src.modules.user.application.ports.google_oauth_service_interface import GoogleUserInfo
from src.modules.user.application.use_cases.google_login_use_case import GoogleLoginUseCase
from src.modules.user.application.use_cases.reset_password_use_case import (
    ResetPasswordUseCase,
)
from src.modules.user.application.use_cases.unlink_google_account_use_case import (
    UnlinkGoogleAccountUseCase,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.exceptions import AccountDeactivatedException
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.infrastructure.security.security_audit_logger import SecurityAuditLogger
from src.shared.infrastructure.security.jwt_handler import JWTTokenService

pytestmark = pytest.mark.asyncio

ADMIN = "5f0c8a2e-1b3d-4e6f-9a7b-2c4d6e8f0a1b"
LINUX = "Mozilla/5.0 (X11; Linux x86_64) Firefox/131.0"
INFO = GoogleUserInfo(
    google_user_id="google-de-ana",
    email="ana@example.com",
    first_name="Ana",
    last_name="Dueña",
    email_verified=True,
)


async def _ana(uow, verificada=True, con_google=False) -> User:
    ana = User.create(
        first_name="Ana",
        last_name="Dueña",
        email_str="ana@example.com",
        plain_password="SecureP@ssw0rd123!",
    )
    if verificada:
        ana.confirm_email_ownership()
    async with uow:
        await uow.users.save(ana)
        if con_google:
            await uow.oauth_accounts.save(
                UserOAuthAccount.create(
                    user_id=ana.id,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id=INFO.google_user_id,
                    provider_email=INFO.email,
                )
            )
    return ana


def _registro_que_a_la_vez(uow, ana: User, que_pasa):
    """El registro del dispositivo de este login, que a la vez cambia la cuenta (otra
    petición) y deja en el repositorio OTRA copia: solo la ve quien relee."""
    dispositivo = UserDevice.create(
        user_id=ana.id, fingerprint=DeviceFingerprint.create(LINUX, "198.51.100.9")
    )

    async def a_la_vez(*_a, **_k):
        async with uow:
            await uow.user_devices.save(dispositivo)
            otra = copy.deepcopy(uow.users._users[ana.id])
            uow.users._users[ana.id] = otra
            await que_pasa(otra)
        return RegisterDeviceResponseDTO(
            device_id=str(dispositivo.id.value), is_new_device=True, message="Nuevo"
        )

    registro = AsyncMock()
    registro.execute.side_effect = a_la_vez
    return registro, dispositivo


def _google(uow, registro):
    servicio = AsyncMock()
    servicio.exchange_code_for_user_info.return_value = INFO
    return GoogleLoginUseCase(
        uow=uow,
        token_service=JWTTokenService(),
        google_oauth_service=servicio,
        register_device_use_case=registro,
        aviso_de_nuevo_inicio=AsyncMock(),
        security_audit=SecurityAuditLogger(),
        email_service=AsyncMock(),
    )


async def _sin_sesion_y_dispositivo_revocado(uow, ana, dispositivo):
    async with uow:
        assert await uow.refresh_tokens.find_all_by_user(ana.id) == []
        assert not (await uow.user_devices.find_by_id(dispositivo.id)).is_active


async def test_a2_google_unlinked_mid_login_gets_no_session():
    """
    Given: Ana con su Google vinculado
    When: Mientras entra con él, otra petición le quita ese Google (una toma)
    Then: Error y sin sesión; el dispositivo de este login, revocado
    """
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow, con_google=True)

    async def le_quitan_el_google(_otra):
        vinculo = await uow.oauth_accounts.find_by_user_id_and_provider(
            ana.id, OAuthProvider.GOOGLE
        )
        await uow.oauth_accounts.delete(vinculo)

    registro, dispositivo = _registro_que_a_la_vez(uow, ana, le_quitan_el_google)

    with pytest.raises(ValueError):
        await _google(uow, registro).execute(GoogleLoginRequestDTO(authorization_code="code"))

    await _sin_sesion_y_dispositivo_revocado(uow, ana, dispositivo)


async def test_a3_deactivated_mid_google_login_gets_403_and_no_session():
    """Si la desactivan mientras entra con Google: 403 y sin sesión."""
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow, con_google=True)

    async def la_desactivan(otra):
        otra.deactivate(deactivated_by_user_id=ADMIN)

    registro, dispositivo = _registro_que_a_la_vez(uow, ana, la_desactivan)

    with pytest.raises(AccountDeactivatedException):
        await _google(uow, registro).execute(GoogleLoginRequestDTO(authorization_code="code"))

    await _sin_sesion_y_dispositivo_revocado(uow, ana, dispositivo)


async def test_b2_resetting_a_verified_account_also_revokes_its_devices():
    """
    Given: Una cuenta verificada con un dispositivo y una sesión
    When: Restablece la contraseña
    Then: Sesión Y dispositivo revocados: un acceso robado no sigue valiendo 15 minutos
    """
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    token = ana.generate_password_reset_token()
    dispositivo = UserDevice.create(
        user_id=ana.id, fingerprint=DeviceFingerprint.create(LINUX, "198.51.100.9")
    )
    async with uow:
        await uow.users.save(ana)
        await uow.user_devices.save(dispositivo)
        await uow.refresh_tokens.save(
            RefreshToken.create(
                user_id=ana.id, token="de-antes", device_id=dispositivo.id, expires_in_days=7
            )
        )

    await ResetPasswordUseCase(uow, AsyncMock(), security_audit=SecurityAuditLogger()).execute(
        ResetPasswordRequestDTO(token=token, new_password="OtraClave#2026segura")
    )

    async with uow:
        assert (await uow.refresh_tokens.find_by_token_hash("de-antes")).revoked
        assert not (await uow.user_devices.find_by_id(dispositivo.id)).is_active


async def _espia_del_bloqueo(uow):
    pedidos = []
    original = uow.users.find_by_id_for_update

    async def espia(user_id):
        pedidos.append(user_id)
        return await original(user_id)

    uow.users.find_by_id_for_update = espia
    return pedidos


async def test_b3_google_locks_a_verified_account_too_before_linking():
    """La toma o el vínculo por correo bloquean la fila también si estaba verificada."""
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    pedidos = await _espia_del_bloqueo(uow)
    registro = AsyncMock()
    registro.execute.return_value = RegisterDeviceResponseDTO(
        device_id="550e8400-e29b-41d4-a716-446655440099", is_new_device=True, message="Nuevo"
    )

    await _google(uow, registro).execute(GoogleLoginRequestDTO(authorization_code="code"))

    assert ana.id in pedidos


async def test_b5_unlinking_google_reads_the_account_with_the_row_locked():
    """
    Given: Ana con contraseña y su Google
    When: Desvincula Google
    Then: Se mira la contraseña sobre la fila bloqueada: una toma a la vez (que la
          quita) no la deja sin ninguna forma de entrar
    """
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow, con_google=True)
    pedidos = await _espia_del_bloqueo(uow)

    await UnlinkGoogleAccountUseCase(uow, email_service=AsyncMock()).execute(str(ana.id.value))

    assert pedidos == [ana.id]


def test_b7_changing_the_email_drops_the_old_verification_link():
    """
    Given: Una cuenta con su enlace de verificación del alta, sin usar
    When: El administrador le cambia el correo
    Then: Ese enlace ya no vale: verificaría el correo nuevo sin que nadie lo demuestre
    """
    ana = User.create(
        first_name="Ana",
        last_name="Dueña",
        email_str="ana@example.com",
        plain_password="SecureP@ssw0rd123!",
    )
    ana.generate_verification_token()

    ana.change_email("otra@example.com")

    assert ana.verification_token is None


async def test_a2_google_relinked_to_another_account_mid_login_gets_no_session():
    """
    Given: Ana con su Google vinculado
    When: Mientras entra, ese Google pasa a estar vinculado a OTRA cuenta
    Then: Sin sesión en la de Ana: el Google ya no es de su cuenta
    """
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow, con_google=True)
    otra = User.create(
        first_name="Otra",
        last_name="Cuenta",
        email_str="otra@example.com",
        plain_password="SecureP@ssw0rd123!",
    )
    async with uow:
        await uow.users.save(otra)

    async def pasa_a_otra(_copia):
        vinculo = await uow.oauth_accounts.find_by_user_id_and_provider(
            ana.id, OAuthProvider.GOOGLE
        )
        await uow.oauth_accounts.delete(vinculo)
        await uow.oauth_accounts.save(
            UserOAuthAccount.create(
                user_id=otra.id,
                provider=OAuthProvider.GOOGLE,
                provider_user_id=INFO.google_user_id,
                provider_email=INFO.email,
            )
        )

    registro, dispositivo = _registro_que_a_la_vez(uow, ana, pasa_a_otra)

    with pytest.raises(ValueError, match="Google unlinked during sign-in"):
        await _google(uow, registro).execute(GoogleLoginRequestDTO(authorization_code="code"))

    await _sin_sesion_y_dispositivo_revocado(uow, ana, dispositivo)


async def test_two_first_google_sign_ins_at_once_do_not_link_twice():
    """
    Given: Ana verificada, sin Google, y dos logins con Google a la vez (dos pestañas)
    When: El segundo llega cuando el primero ya vinculó el Google
    Then: El segundo ve el vínculo bajo el bloqueo y no lo crea otra vez (antes, un
          500 por la restricción única)
    """
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    original = uow.users.find_by_id_for_update

    async def el_otro_ya_lo_vinculo(user_id):
        if (
            await uow.oauth_accounts.find_by_user_id_and_provider(user_id, OAuthProvider.GOOGLE)
            is None
        ):
            await uow.oauth_accounts.save(
                UserOAuthAccount.create(
                    user_id=user_id,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id=INFO.google_user_id,
                    provider_email=INFO.email,
                )
            )
        return await original(user_id)

    uow.users.find_by_id_for_update = el_otro_ya_lo_vinculo
    registro = AsyncMock()
    registro.execute.return_value = RegisterDeviceResponseDTO(
        device_id="550e8400-e29b-41d4-a716-446655440099", is_new_device=True, message="Nuevo"
    )

    await _google(uow, registro).execute(GoogleLoginRequestDTO(authorization_code="code"))

    vinculos = [v for v in uow.oauth_accounts._accounts.values() if v.user_id == ana.id]
    assert len(vinculos) == 1


async def test_a_google_linked_to_another_account_meanwhile_is_a_plain_refusal():
    """
    Given: Ana verificada, sin Google; mientras entra, ese Google se vincula a OTRA cuenta
    When: Google iba a vincularse a Ana por el correo
    Then: Un rechazo (ValueError), no un vínculo duplicado que reviente en la BD (500)
    """
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    otra = User.create(
        first_name="Otra",
        last_name="Cuenta",
        email_str="otra@example.com",
        plain_password="SecureP@ssw0rd123!",
    )
    async with uow:
        await uow.users.save(otra)
    original = uow.users.find_by_id_for_update

    async def a_otra(user_id):
        if (
            await uow.oauth_accounts.find_by_provider_and_provider_user_id(
                OAuthProvider.GOOGLE, INFO.google_user_id
            )
            is None
        ):
            await uow.oauth_accounts.save(
                UserOAuthAccount.create(
                    user_id=otra.id,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id=INFO.google_user_id,
                    provider_email=INFO.email,
                )
            )
        return await original(user_id)

    uow.users.find_by_id_for_update = a_otra
    registro = AsyncMock()

    with pytest.raises(ValueError, match="Google account already linked to another user"):
        await _google(uow, registro).execute(GoogleLoginRequestDTO(authorization_code="code"))

    assert [v for v in uow.oauth_accounts._accounts.values() if v.user_id == ana.id] == []
