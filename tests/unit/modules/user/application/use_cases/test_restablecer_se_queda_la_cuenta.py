"""
Restablecer la contraseña de una cuenta SIN verificar se la queda, como Google (#749).

El enlace llega al buzón del correo de la cuenta: quien lo usa demuestra que el
correo es suyo. Lo que dejó quien creó la cuenta o le cambió el correo (un Google
vinculado, sus dispositivos, sus sesiones) no se probó y se quita.

  #   Caso                                         | Resultado
  ----|--------------------------------------------|---------------------------------------
  R1  sin verificar, con un Google ajeno, sesiones | verificada, la contraseña nueva, sin ese
                                                   |   Google, dispositivos y sesiones fuera
  R2  ya verificada, con un Google                | sin ese Google (BE #753); sesiones y
                                                   |   dispositivos, fuera (tabla de caminos)
  R3  la toma                                      | al log de seguridad, con lo que se cerró;
                                                   |   un log roto no cambia el restablecimiento
  R6  la toma (BE #753, punto 6)                   | en vez de «contraseña cambiada», el aviso
                                                   |   de cuenta asegurada, «por restablecimiento»
  R6b ya verificada                                | «contraseña cambiada», como hoy
  R6c el aviso falla                               | el restablecimiento se queda
"""

from unittest.mock import AsyncMock

import pytest

from src.modules.user.application.dto.user_dto import ResetPasswordRequestDTO
from src.modules.user.application.use_cases.reset_password_use_case import (
    ResetPasswordUseCase,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.infrastructure.security.security_audit_logger import SecurityAuditLogger

pytestmark = pytest.mark.asyncio

NUEVA = "OtraClave#2026segura"


async def _escena(verificada: bool):
    uow = InMemoryUnitOfWork()
    cuenta = User.create(
        first_name="Ana",
        last_name="Dueña",
        email_str="ana@example.com",
        plain_password="Vieja#2026clave",
    )
    if verificada:
        cuenta.confirm_email_ownership()
    token = cuenta.generate_password_reset_token()
    dispositivo = UserDevice.create(
        user_id=cuenta.id,
        fingerprint=DeviceFingerprint.create(
            "Mozilla/5.0 (X11; Linux x86_64) Firefox/131.0", "198.51.100.9"
        ),
    )
    async with uow:
        await uow.users.save(cuenta)
        await uow.user_devices.save(dispositivo)
        await uow.refresh_tokens.save(
            RefreshToken.create(
                user_id=cuenta.id,
                token="sesion-de-antes",
                device_id=dispositivo.id,
                expires_in_days=7,
            )
        )
        await uow.oauth_accounts.save(
            UserOAuthAccount.create(
                user_id=cuenta.id,
                provider=OAuthProvider.GOOGLE,
                provider_user_id="google-de-otro",
                provider_email="otro@example.com",
            )
        )
    return (
        uow,
        cuenta,
        dispositivo,
        ResetPasswordUseCase(uow, AsyncMock(), security_audit=SecurityAuditLogger()),
        token,
    )


async def _restablece(caso, token):
    return await caso.execute(
        ResetPasswordRequestDTO(
            token=token, new_password=NUEVA, ip_address="203.0.113.7", user_agent="Navegador"
        )
    )


async def test_r1_an_unverified_account_is_claimed_by_whoever_resets_it():
    """
    Given: Una cuenta sin verificar, con un Google vinculado, un dispositivo y una sesión
    When: Se restablece la contraseña con el enlace del correo
    Then: Verificada, con la contraseña nueva, sin ese Google, el dispositivo revocado y la
          sesión revocada
    """
    uow, cuenta, dispositivo, caso, token = await _escena(verificada=False)

    await _restablece(caso, token)

    async with uow:
        guardada = await uow.users.find_by_id(cuenta.id)
        assert guardada.email_verified
        assert guardada.verify_password(NUEVA)
        assert (
            await uow.oauth_accounts.find_by_user_id_and_provider(cuenta.id, OAuthProvider.GOOGLE)
            is None
        )
        assert not (await uow.user_devices.find_by_id(dispositivo.id)).is_active
        assert (await uow.refresh_tokens.find_by_token_hash("sesion-de-antes")).revoked


async def test_r2_a_verified_account_also_loses_its_google():
    """
    Given: Una cuenta verificada, con un Google y un dispositivo
    When: Se restablece la contraseña
    Then: Sin ese Google (pudo vincularlo quien entró en la cuenta: BE #753, Agustín);
          sesiones y dispositivos, revocados. Quien lo tenga de verdad lo vuelve a vincular
    """
    uow, cuenta, dispositivo, caso, token = await _escena(verificada=True)

    await _restablece(caso, token)

    async with uow:
        assert (
            await uow.oauth_accounts.find_by_user_id_and_provider(cuenta.id, OAuthProvider.GOOGLE)
            is None
        )
        assert not (await uow.user_devices.find_by_id(dispositivo.id)).is_active
        assert (await uow.refresh_tokens.find_by_token_hash("sesion-de-antes")).revoked


async def test_r3_the_claim_goes_to_the_security_log(monkeypatch):
    """La toma por restablecimiento, al log, con lo que se cerró y por dónde."""
    from src.shared.infrastructure.logging import security_logger as modulo

    apuntes = []
    monkeypatch.setattr(
        modulo.SecurityLogger,
        "log_unverified_account_claimed",
        lambda self, **kw: apuntes.append(kw),
    )
    _uow, cuenta, _d, caso, token = await _escena(verificada=False)

    await _restablece(caso, token)

    assert apuntes == [
        {
            "user_id": str(cuenta.id.value),
            "devices_revoked": 1,
            "tokens_revoked": 1,
            "google_unlinked": 1,
            "via": "password_reset",
            "ip_address": "203.0.113.7",
            "user_agent": "Navegador",
        }
    ]


async def test_r3_a_broken_log_does_not_undo_the_reset(monkeypatch):
    """Si el log falla, la contraseña queda cambiada y la cuenta tomada igual."""
    from src.shared.infrastructure.logging import security_logger as modulo

    def roto(self, **kw):
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(modulo.SecurityLogger, "log_unverified_account_claimed", roto)
    uow, cuenta, _d, caso, token = await _escena(verificada=False)

    await _restablece(caso, token)

    async with uow:
        assert (await uow.users.find_by_id(cuenta.id)).verify_password(NUEVA)


async def test_r4_a_claim_right_before_the_lock_wins_over_the_reset():
    """
    Given: Una cuenta sin verificar con su enlace de restablecer
    When: Justo antes de que el restablecimiento bloquee la fila, Google se la queda
          (borra el token)
    Then: El enlace ya no vale (token inválido) y lo de Google se queda: el
          restablecimiento no le quita el Google recién vinculado
    """
    import copy

    from src.modules.user.domain.exceptions.invalid_reset_token_error import InvalidResetTokenError

    uow, cuenta, _d, caso, token = await _escena(verificada=False)

    async def tomada(user_id):
        # La toma de Google, a la vez: se queda la cuenta y vincula SU Google
        otra = copy.deepcopy(uow.users._users[user_id])
        otra.claim_with_verified_oauth()
        uow.users._users[user_id] = otra
        anterior = await uow.oauth_accounts.find_by_user_id_and_provider(
            user_id, OAuthProvider.GOOGLE
        )
        await uow.oauth_accounts.delete(anterior)
        await uow.oauth_accounts.save(
            UserOAuthAccount.create(
                user_id=user_id,
                provider=OAuthProvider.GOOGLE,
                provider_user_id="google-del-dueno",
                provider_email="ana@example.com",
            )
        )
        return otra

    uow.users.find_by_id_for_update = tomada

    with pytest.raises(InvalidResetTokenError):
        await _restablece(caso, token)

    async with uow:
        suyo = await uow.oauth_accounts.find_by_user_id_and_provider(
            cuenta.id, OAuthProvider.GOOGLE
        )
        assert suyo.provider_user_id == "google-del-dueno"


async def test_r5_any_reset_cancels_a_pending_email_change():
    """
    Given: Una cuenta verificada con un cambio de correo pendiente
    When: Restablece la contraseña (quizá porque alguien entró en ella)
    Then: El pendiente se anula: quien lo pidiera ya no se la lleva
    """
    from datetime import datetime

    uow, cuenta, _d, caso, token = await _escena(verificada=True)
    cuenta.request_email_change("otro@example.com", ahora=datetime.now())
    async with uow:
        await uow.users.save(cuenta)

    await _restablece(caso, token)

    async with uow:
        assert (await uow.users.find_by_id(cuenta.id)).pending_email_token is None


async def test_r6_a_claim_sends_the_secured_notice_instead():
    """
    Given: Una cuenta sin verificar
    When: Se restablece la contraseña con el enlace
    Then: El aviso de cuenta asegurada, por restablecimiento, y no el de contraseña cambiada
    """
    _uow, _cuenta, _d, caso, token = await _escena(verificada=False)

    await _restablece(caso, token)

    caso._email_service.send_account_secured_notice.assert_awaited_once_with(
        to_email="ana@example.com", user_name="Ana", via="reset"
    )
    caso._email_service.send_password_changed_notification.assert_not_awaited()


async def test_r6b_a_verified_account_gets_the_usual_notice():
    """Sin toma, el aviso de siempre."""
    _uow, _cuenta, _d, caso, token = await _escena(verificada=True)

    await _restablece(caso, token)

    caso._email_service.send_account_secured_notice.assert_not_awaited()
    caso._email_service.send_password_changed_notification.assert_awaited_once()


async def test_r6c_a_failing_notice_keeps_the_reset():
    """El aviso no deshace el restablecimiento, ya guardado."""
    uow, cuenta, _d, caso, token = await _escena(verificada=False)
    caso._email_service.send_account_secured_notice.side_effect = RuntimeError("smtp")

    await _restablece(caso, token)

    async with uow:
        assert (await uow.users.find_by_id(cuenta.id)).verify_password(NUEVA)


async def test_r2b_removing_the_google_on_a_reset_is_recorded():
    """La desvinculación queda como evento, igual que al desvincular a mano (code-review)."""
    from src.modules.user.domain.events.google_account_unlinked_event import (
        GoogleAccountUnlinkedEvent,
    )

    uow, cuenta, _d, caso, token = await _escena(verificada=True)

    await _restablece(caso, token)

    async with uow:
        guardada = await uow.users.find_by_id(cuenta.id)
    assert any(isinstance(e, GoogleAccountUnlinkedEvent) for e in guardada.get_domain_events())
