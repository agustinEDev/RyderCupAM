"""
Restablecer la contraseña de una cuenta SIN verificar se la queda, como Google (#749).

El enlace llega al buzón del correo de la cuenta: quien lo usa demuestra que el
correo es suyo. Lo que dejó quien creó la cuenta o le cambió el correo (un Google
vinculado, sus dispositivos, sus sesiones) no se probó y se quita.

  #   Caso                                         | Resultado
  ----|--------------------------------------------|---------------------------------------
  R1  sin verificar, con un Google ajeno, sesiones | verificada, la contraseña nueva, sin ese
                                                   |   Google, dispositivos y sesiones fuera
  R2  ya verificada, con su Google                 | conserva su Google; sesiones y dispositivos,
                                                   |   fuera (tabla de caminos)
  R3  la toma                                      | al log de seguridad, con lo que se cerró;
                                                   |   un log roto no cambia el restablecimiento
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
    return uow, cuenta, dispositivo, ResetPasswordUseCase(uow, AsyncMock()), token


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


async def test_r2_a_verified_account_keeps_its_google():
    """
    Given: Una cuenta verificada, con su Google y un dispositivo
    When: Se restablece la contraseña
    Then: Conserva su Google (es suyo); sesiones y dispositivos, revocados
    """
    uow, cuenta, dispositivo, caso, token = await _escena(verificada=True)

    await _restablece(caso, token)

    async with uow:
        assert await uow.oauth_accounts.find_by_user_id_and_provider(
            cuenta.id, OAuthProvider.GOOGLE
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
