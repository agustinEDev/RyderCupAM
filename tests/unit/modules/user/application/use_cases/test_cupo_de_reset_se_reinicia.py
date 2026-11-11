"""
El cupo de 10 correos de restablecer al día vuelve a cero cuando la cuenta demuestra
que es suya (fase 3, M-2, decidido por Agustín): al iniciar sesión (contraseña o
Google) o al restablecer la contraseña.

  #   Caso                                       | Resultado
  ----|-------------------------------------------|----------------------------------
  M2  cuenta con el cupo gastado restablece      | cupo a cero (y ventana fuera)
  M2  inicia sesión con Google                   | cupo a cero
  M2  inicia sesión con contraseña               | cupo a cero (integración:
                                                 |   test_registro_y_enlaces)
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.user.application.dto.device_dto import RegisterDeviceResponseDTO
from src.modules.user.application.dto.oauth_dto import GoogleLoginRequestDTO
from src.modules.user.application.dto.user_dto import ResetPasswordRequestDTO
from src.modules.user.application.ports.google_oauth_service_interface import GoogleUserInfo
from src.modules.user.application.use_cases.google_login_use_case import GoogleLoginUseCase
from src.modules.user.application.use_cases.reset_password_use_case import ResetPasswordUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.infrastructure.security.security_audit_logger import SecurityAuditLogger
from src.shared.infrastructure.security.jwt_handler import JWTTokenService

pytestmark = pytest.mark.asyncio

NUEVA = "N3wS3cur3P@ss!"


def _gasta_el_cupo(user: User) -> None:
    for _ in range(10):
        user.cuenta_un_correo_de_reset(datetime.now())
    assert user.cuenta_un_correo_de_reset(datetime.now()) is False


def test_m2_the_entity_resets_the_quota():
    """
    Given: Una cuenta con el cupo gastado
    When: Se reinicia el cupo
    Then: Cuenta cero y vuelve a caber un correo
    """
    user = User.create("Ana", "Lopez", "ana@example.com", "SecureP@ssw0rd123!")
    _gasta_el_cupo(user)

    user.reinicia_el_cupo_de_reset()

    assert user.password_reset_emails_in_window == 0
    assert user.password_reset_window_started_at is None
    assert user.cuenta_un_correo_de_reset(datetime.now()) is True


async def test_m2_resetting_the_password_resets_the_quota():
    """
    Given: Una cuenta con el cupo gastado y un enlace vigente
    When: Restablece la contraseña con él
    Then: Cupo a cero
    """
    uow = InMemoryUnitOfWork()
    user = User.create("Ana", "Lopez", "ana@example.com", "SecureP@ssw0rd123!")
    user.confirm_email_ownership()
    token = user.generate_password_reset_token()
    _gasta_el_cupo(user)
    async with uow:
        await uow.users.save(user)
    correo = MagicMock()
    correo.send_password_changed_notification = AsyncMock(return_value=True)

    await ResetPasswordUseCase(uow, correo, security_audit=MagicMock()).execute(
        ResetPasswordRequestDTO(token=token, new_password=NUEVA)
    )

    assert user.password_reset_emails_in_window == 0


async def test_m2_signing_in_with_google_resets_the_quota():
    """
    Given: Una cuenta con Google vinculado y el cupo gastado
    When: Inicia sesión con Google
    Then: Cupo a cero
    """
    uow = InMemoryUnitOfWork()
    user = User.create_from_oauth(first_name="Ana", last_name="Lopez", email_str="g@example.com")
    _gasta_el_cupo(user)
    async with uow:
        await uow.users.save(user)
        await uow.oauth_accounts.save(
            UserOAuthAccount.create(
                user_id=user.id,
                provider=OAuthProvider.GOOGLE,
                provider_user_id="google-id-1",
                provider_email="g@example.com",
            )
        )
    google = AsyncMock()
    google.exchange_code_for_user_info.return_value = GoogleUserInfo(
        google_user_id="google-id-1",
        email="g@example.com",
        first_name="Ana",
        last_name="Lopez",
        email_verified=True,
        picture_url=None,
    )
    dispositivos = AsyncMock()
    dispositivos.execute.return_value = RegisterDeviceResponseDTO(
        device_id="550e8400-e29b-41d4-a716-446655440099",
        is_new_device=True,
        message="New device registered",
    )
    caso = GoogleLoginUseCase(
        uow=uow,
        token_service=JWTTokenService(),
        google_oauth_service=google,
        register_device_use_case=dispositivos,
        aviso_de_nuevo_inicio=AsyncMock(),
        security_audit=SecurityAuditLogger(),
        email_service=AsyncMock(),
    )

    await caso.execute(
        GoogleLoginRequestDTO(
            authorization_code="code", ip_address="1.2.3.4", user_agent="UA", code_verifier="v" * 43
        )
    )

    assert user.password_reset_emails_in_window == 0
