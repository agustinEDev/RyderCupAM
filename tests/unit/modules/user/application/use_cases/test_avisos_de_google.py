"""
Los avisos al vincular y desvincular Google (BE #753, punto 2).

Un Google vinculado da acceso a la cuenta: su dueño tiene que enterarse.

  A1 vincular bien: aviso al correo de la cuenta, «vinculado»
  A2 desvincular bien: aviso, «desvinculado»
  A3 el aviso falla o no sale: la operación se queda
  A4 vincular que no sale bien (ya vinculado a otro): sin aviso
  A5 desvincular en una cuenta sin verificar: sin aviso (nunca a un correo sin confirmar)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.user.application.dto.oauth_dto import (
    LinkGoogleAccountRequestDTO,
    UnlinkGoogleAccountRequestDTO,
)
from src.modules.user.application.ports.google_oauth_service_interface import GoogleUserInfo
from src.modules.user.application.use_cases.link_google_account_use_case import (
    LinkGoogleAccountUseCase,
)
from src.modules.user.application.use_cases.unlink_google_account_use_case import (
    UnlinkGoogleAccountUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio


async def _ana(uow, verificada=True, con_google=False) -> User:
    ana = User.create(
        first_name="Ana",
        last_name="Lopez",
        email_str="ana@example.com",
        plain_password="V@l1dP@ss123!",
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
                    provider_user_id="google-ana",
                    provider_email="ana@gmail.com",
                )
            )
    return ana


def _google(google_id="google-ana") -> AsyncMock:
    google = AsyncMock()
    google.exchange_code_for_user_info.return_value = GoogleUserInfo(
        google_user_id=google_id,
        email="ana@gmail.com",
        first_name="Ana",
        last_name="Lopez",
        email_verified=True,
        picture_url=None,
    )
    return google


async def _vincula(uow, ana, correos, google=None):
    return await LinkGoogleAccountUseCase(
        uow, google or _google(), security_audit=MagicMock(), email_service=correos
    ).execute(
        LinkGoogleAccountRequestDTO(authorization_code="c"), str(ana.id.value), reautenticado=True
    )


async def test_a1_linking_tells_the_account():
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    correos = AsyncMock()

    await _vincula(uow, ana, correos)

    correos.send_google_account_notice.assert_awaited_once_with(
        to_email="ana@example.com", user_name="Ana", linked=True
    )


async def test_a2_unlinking_tells_the_account():
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow, con_google=True)
    correos = AsyncMock()

    await UnlinkGoogleAccountUseCase(
        uow, email_service=correos, security_audit=MagicMock()
    ).execute(UnlinkGoogleAccountRequestDTO(user_id=str(ana.id.value)), reautenticado=True)

    correos.send_google_account_notice.assert_awaited_once_with(
        to_email="ana@example.com", user_name="Ana", linked=False
    )


@pytest.mark.parametrize("falla", ["lanza", "no sale"])
async def test_a3_a_failing_notice_keeps_the_link_and_the_unlink(falla):
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    correos = AsyncMock()
    if falla == "lanza":
        correos.send_google_account_notice.side_effect = RuntimeError("smtp")
    else:
        correos.send_google_account_notice.return_value = False

    await _vincula(uow, ana, correos)
    await UnlinkGoogleAccountUseCase(
        uow, email_service=correos, security_audit=MagicMock()
    ).execute(UnlinkGoogleAccountRequestDTO(user_id=str(ana.id.value)), reautenticado=True)

    async with uow:
        assert (
            await uow.oauth_accounts.find_by_user_id_and_provider(ana.id, OAuthProvider.GOOGLE)
            is None
        )
    assert correos.send_google_account_notice.await_count == 2


async def test_a4_a_failed_link_tells_nobody():
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    otra = await _ana(InMemoryUnitOfWork())
    async with uow:
        await uow.oauth_accounts.save(
            UserOAuthAccount.create(
                user_id=otra.id,
                provider=OAuthProvider.GOOGLE,
                provider_user_id="google-ana",
                provider_email="ana@gmail.com",
            )
        )
    correos = AsyncMock()

    with pytest.raises(ValueError):
        await _vincula(uow, ana, correos)

    correos.send_google_account_notice.assert_not_awaited()


async def test_a5_an_unverified_account_is_not_told_on_unlink():
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow, verificada=False, con_google=True)
    correos = AsyncMock()

    await UnlinkGoogleAccountUseCase(
        uow, email_service=correos, security_audit=MagicMock()
    ).execute(UnlinkGoogleAccountRequestDTO(user_id=str(ana.id.value)), reautenticado=True)

    correos.send_google_account_notice.assert_not_awaited()
