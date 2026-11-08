"""
Tests para UnlinkGoogleAccountUseCase

Tests unitarios para el caso de uso de desvincular cuenta Google.
"""

from unittest.mock import AsyncMock

import pytest

from src.modules.user.application.use_cases.unlink_google_account_use_case import (
    UnlinkGoogleAccountUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def use_case(uow):
    return UnlinkGoogleAccountUseCase(uow=uow, email_service=AsyncMock())


@pytest.fixture
async def user_with_password(uow):
    """Usuario con password Y cuenta Google vinculada."""
    user = User.create(
        first_name="Has",
        last_name="Password",
        email_str="password@example.com",
        plain_password="V@l1dP@ss123!",
    )
    async with uow:
        await uow.users.save(user)

    oauth = UserOAuthAccount.create(
        user_id=user.id,
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-unlink-123",
        provider_email="password@gmail.com",
    )
    async with uow:
        await uow.oauth_accounts.save(oauth)

    return user


@pytest.fixture
async def oauth_only_user(uow):
    """Usuario sin password (creado via OAuth)."""
    user = User.create_from_oauth(
        first_name="OAuth",
        last_name="Only",
        email_str="oauthonly@example.com",
    )
    async with uow:
        await uow.users.save(user)

    oauth = UserOAuthAccount.create(
        user_id=user.id,
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-oauth-only",
        provider_email="oauthonly@gmail.com",
    )
    async with uow:
        await uow.oauth_accounts.save(oauth)

    return user


@pytest.mark.asyncio
class TestUnlinkGoogleAccountUseCase:
    """Tests para desvincular cuenta Google."""

    async def test_unlink_google_account_successfully(self, use_case, uow, user_with_password):
        """Debe desvincular Google cuando el usuario tiene password."""
        response = await use_case.execute(str(user_with_password.id.value))

        assert response.message == "Google account unlinked successfully"
        assert response.provider == "google"

        # Verificar que ya no existe la OAuth account
        oauth = await uow.oauth_accounts.find_by_user_id_and_provider(
            user_with_password.id, OAuthProvider.GOOGLE
        )
        assert oauth is None

    async def test_unlink_fails_when_no_google_linked(self, use_case, uow):
        """Debe fallar si el usuario no tiene cuenta Google vinculada."""
        user = User.create(
            first_name="No",
            last_name="Google",
            email_str="nogoogle@example.com",
            plain_password="V@l1dP@ss123!",
        )
        async with uow:
            await uow.users.save(user)

        with pytest.raises(ValueError, match="No Google account linked"):
            await use_case.execute(str(user.id.value))

    async def test_unlink_fails_when_oauth_only_user(self, use_case, oauth_only_user):
        """Debe fallar si el usuario no tiene password (único método auth)."""
        with pytest.raises(ValueError, match="only authentication method"):
            await use_case.execute(str(oauth_only_user.id.value))

    async def test_unlink_fails_when_user_not_found(self, use_case, uow):
        """Debe fallar cuando el usuario no existe."""
        # Crear OAuth account sin usuario correspondiente
        from src.modules.user.domain.value_objects.user_id import UserId

        fake_id = UserId.generate()
        oauth = UserOAuthAccount.create(
            user_id=fake_id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-fake",
            provider_email="fake@gmail.com",
        )
        async with uow:
            await uow.oauth_accounts.save(oauth)

        with pytest.raises(ValueError, match="User not found"):
            await use_case.execute(str(fake_id.value))

    async def test_unlink_emits_domain_event(self, use_case, user_with_password):
        """Debe emitir GoogleAccountUnlinkedEvent en el usuario."""
        await use_case.execute(str(user_with_password.id.value))

        from src.modules.user.domain.events.google_account_unlinked_event import (
            GoogleAccountUnlinkedEvent,
        )

        events = user_with_password.get_domain_events()
        unlinked_events = [e for e in events if isinstance(e, GoogleAccountUnlinkedEvent)]
        assert len(unlinked_events) == 1
        assert unlinked_events[0].provider == "google"


@pytest.mark.asyncio
async def test_the_google_link_is_looked_up_after_locking_the_account():
    """
    Given: Una cuenta con su Google
    When: Se desvincula
    Then: El vínculo se busca con la fila ya bloqueada: dos desvinculaciones a la vez no
          dicen las dos «hecho» (CodeRabbit en #752)
    """
    from src.modules.user.application.use_cases.unlink_google_account_use_case import (
        UnlinkGoogleAccountUseCase,
    )
    from src.modules.user.domain.entities.user import User
    from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
    from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
    from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
        InMemoryUnitOfWork,
    )

    uow = InMemoryUnitOfWork()
    ana = User.create(
        first_name="Ana",
        last_name="Dueña",
        email_str="ana@example.com",
        plain_password="SecureP@ssw0rd123!",
    )
    async with uow:
        await uow.users.save(ana)
        await uow.oauth_accounts.save(
            UserOAuthAccount.create(
                user_id=ana.id,
                provider=OAuthProvider.GOOGLE,
                provider_user_id="g",
                provider_email="ana@example.com",
            )
        )
    orden = []
    bloqueo, busca = (
        uow.users.find_by_id_for_update,
        uow.oauth_accounts.find_by_user_id_and_provider,
    )

    async def espia_bloqueo(user_id):
        orden.append("bloqueo")
        return await bloqueo(user_id)

    async def espia_busca(*a):
        orden.append("busca")
        return await busca(*a)

    uow.users.find_by_id_for_update = espia_bloqueo
    uow.oauth_accounts.find_by_user_id_and_provider = espia_busca

    await UnlinkGoogleAccountUseCase(uow, email_service=AsyncMock()).execute(str(ana.id.value))

    assert orden == ["bloqueo", "busca"]
