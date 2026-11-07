"""
Tests para LinkGoogleAccountUseCase

Tests unitarios para el caso de uso de vincular cuenta Google a usuario existente.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.user.application.dto.oauth_dto import LinkGoogleAccountRequestDTO
from src.modules.user.application.ports.google_oauth_service_interface import (
    GoogleUserInfo,
)
from src.modules.user.application.use_cases.link_google_account_use_case import (
    GoogleLinkNeedsVerifiedEmailError,
    LinkGoogleAccountUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def google_oauth_service():
    return AsyncMock()


@pytest.fixture
def google_user_info():
    return GoogleUserInfo(
        google_user_id="google-link-123",
        email="link@gmail.com",
        first_name="Link",
        last_name="User",
        email_verified=True,
    )


@pytest.fixture
def auditoria():
    return MagicMock()


@pytest.fixture
def use_case(uow, google_oauth_service, auditoria):
    return LinkGoogleAccountUseCase(
        uow=uow,
        google_oauth_service=google_oauth_service,
        security_audit=auditoria,
    )


@pytest.fixture
async def existing_user(uow):
    user = User.create(
        first_name="Existing",
        last_name="User",
        email_str="existing@example.com",
        plain_password="V@l1dP@ss123!",
    )
    # Verificada: vincular Google la pide (revisión de la pre-captura, #749)
    user.confirm_email_ownership()
    async with uow:
        await uow.users.save(user)
    return user


@pytest.mark.asyncio
class TestLinkGoogleAccountUseCase:
    """Tests para vincular cuenta Google."""

    async def test_link_google_account_successfully(
        self, use_case, uow, google_oauth_service, google_user_info, existing_user
    ):
        """Debe vincular Google account exitosamente."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        request = LinkGoogleAccountRequestDTO(authorization_code="link-code")
        response = await use_case.execute(request, str(existing_user.id.value))

        assert response.message == "Google account linked successfully"
        assert response.provider == "google"
        assert response.provider_email == "link@gmail.com"

        # Verificar que se creó la OAuth account
        oauth = await uow.oauth_accounts.find_by_provider_and_provider_user_id(
            OAuthProvider.GOOGLE, "google-link-123"
        )
        assert oauth is not None
        assert oauth.user_id == existing_user.id

    async def test_link_fails_when_google_account_already_linked_to_another_user(
        self, use_case, uow, google_oauth_service, google_user_info, existing_user
    ):
        """Debe fallar si la cuenta Google ya está vinculada a otro usuario."""
        # Vincular a otro usuario primero
        other_user_id = UserId.generate()
        other_oauth = UserOAuthAccount.create(
            user_id=other_user_id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-link-123",
            provider_email="other@gmail.com",
        )
        async with uow:
            await uow.oauth_accounts.save(other_oauth)

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        request = LinkGoogleAccountRequestDTO(authorization_code="link-code")
        with pytest.raises(ValueError, match="already linked to another user"):
            await use_case.execute(request, str(existing_user.id.value))

    async def test_link_fails_when_user_already_has_google(
        self, use_case, uow, google_oauth_service, google_user_info, existing_user
    ):
        """Debe fallar si el usuario ya tiene una cuenta Google vinculada."""
        # Vincular Google al usuario actual
        existing_oauth = UserOAuthAccount.create(
            user_id=existing_user.id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-old-456",
            provider_email="old@gmail.com",
        )
        async with uow:
            await uow.oauth_accounts.save(existing_oauth)

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        request = LinkGoogleAccountRequestDTO(authorization_code="link-code")
        with pytest.raises(ValueError, match="already have a Google account linked"):
            await use_case.execute(request, str(existing_user.id.value))

    async def test_link_propagates_oauth_service_error(
        self, use_case, google_oauth_service, existing_user
    ):
        """Debe propagar errores del servicio de Google."""
        google_oauth_service.exchange_code_for_user_info.side_effect = ValueError(
            "Invalid authorization code"
        )

        request = LinkGoogleAccountRequestDTO(authorization_code="bad-code")
        with pytest.raises(ValueError, match="Invalid authorization code"):
            await use_case.execute(request, str(existing_user.id.value))

    async def test_link_creates_oauth_account_with_correct_data(
        self, use_case, uow, google_oauth_service, google_user_info, existing_user
    ):
        """Verifica que la OAuth account se crea con datos correctos."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        request = LinkGoogleAccountRequestDTO(authorization_code="link-code")
        await use_case.execute(request, str(existing_user.id.value))

        oauth = await uow.oauth_accounts.find_by_user_id_and_provider(
            existing_user.id, OAuthProvider.GOOGLE
        )
        assert oauth is not None
        assert oauth.provider == OAuthProvider.GOOGLE
        assert oauth.provider_user_id == "google-link-123"
        assert oauth.provider_email == "link@gmail.com"
        assert oauth.user_id == existing_user.id


@pytest.mark.asyncio
async def test_an_unverified_account_cannot_link_google(
    use_case, uow, google_oauth_service, google_user_info
):
    """
    Given: Una cuenta con sesión y el correo SIN verificar (la pudo crear cualquiera)
    When: Vincula Google desde el perfil
    Then: GoogleLinkNeedsVerifiedEmailError y ningún vínculo: si no, quien la creó
          metería su propio Google y se lo quedaría aunque el dueño la recupere
    """
    user = User.create(
        first_name="Sin",
        last_name="Verificar",
        email_str="sinverificar@example.com",
        plain_password="V@l1dP@ss123!",
    )
    async with uow:
        await uow.users.save(user)
    google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

    with pytest.raises(GoogleLinkNeedsVerifiedEmailError):
        await use_case.execute(
            LinkGoogleAccountRequestDTO(authorization_code="code"), str(user.id.value)
        )

    async with uow:
        assert (
            await uow.oauth_accounts.find_by_user_id_and_provider(user.id, OAuthProvider.GOOGLE)
            is None
        )
    # Sin gastar el código con Google: se mira antes
    google_oauth_service.exchange_code_for_user_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_verified_email_is_checked_again_when_linking(
    use_case, uow, google_oauth_service, google_user_info, existing_user
):
    """
    Given: Una cuenta verificada que, mientras se habla con Google, cambia de correo y
           queda sin verificar (otra petición a la vez)
    When: Se guarda el vínculo
    Then: GoogleLinkNeedsVerifiedEmailError: se vuelve a mirar con la fila bloqueada
    """
    import copy

    async def cambia_a_mitad(_code):
        otra = copy.deepcopy(uow.users._users[existing_user.id])
        otra.change_email("otro.correo@example.com")
        uow.users._users[existing_user.id] = otra
        return google_user_info

    google_oauth_service.exchange_code_for_user_info.side_effect = cambia_a_mitad

    with pytest.raises(GoogleLinkNeedsVerifiedEmailError):
        await use_case.execute(
            LinkGoogleAccountRequestDTO(authorization_code="code"), str(existing_user.id.value)
        )

    async with uow:
        assert (
            await uow.oauth_accounts.find_by_user_id_and_provider(
                existing_user.id, OAuthProvider.GOOGLE
            )
            is None
        )


@pytest.mark.asyncio
class TestElVinculoManualAlLog:
    """V1 (#750 punto 3): el vínculo desde el perfil se registra en el caso de uso, como
    el automático, ya guardado y con la red: cualquier uso del caso de uso queda auditado."""

    async def test_v1_a_link_goes_to_the_log_with_the_network(
        self, use_case, existing_user, google_oauth_service, google_user_info, auditoria, uow
    ):
        """
        Given: Un usuario verificado que vincula su Google
        When: Se vincula, con la IP y el navegador
        Then: Al log, manual (no automático), con su red, y ya guardado el vínculo
        """
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info
        guardado_al_registrar = []

        async def guardado():
            async with uow:
                return await uow.oauth_accounts.find_by_user_id_and_provider(
                    existing_user.id, OAuthProvider.GOOGLE
                )

        def apunta(**kw):
            guardado_al_registrar.append(kw)

        auditoria.log_google_account_linked.side_effect = apunta

        await use_case.execute(
            LinkGoogleAccountRequestDTO(
                authorization_code="code", ip_address="203.0.113.7", user_agent="Safari"
            ),
            str(existing_user.id.value),
        )

        assert guardado_al_registrar == [
            {
                "user_id": str(existing_user.id.value),
                "automatic": False,
                "ip_address": "203.0.113.7",
                "user_agent": "Safari",
            }
        ]
        assert await guardado() is not None

    async def test_v1_a_refused_link_is_not_logged_as_linked(
        self, use_case, uow, google_oauth_service, google_user_info, auditoria
    ):
        """
        Given: Un usuario con el correo sin verificar
        When: Intenta vincular Google
        Then: Rechazado, y nada de «vinculado» en el log
        """
        sin_verificar = User.create(
            first_name="Sin",
            last_name="Verificar",
            email_str="sv@example.com",
            plain_password="V@l1dP@ss123!",
        )
        async with uow:
            await uow.users.save(sin_verificar)

        with pytest.raises(GoogleLinkNeedsVerifiedEmailError):
            await use_case.execute(
                LinkGoogleAccountRequestDTO(authorization_code="code"),
                str(sin_verificar.id.value),
            )

        auditoria.log_google_account_linked.assert_not_called()

    async def test_v1_a_broken_log_does_not_undo_the_link(
        self, use_case, existing_user, google_oauth_service, google_user_info, auditoria
    ):
        """
        Given: Un log de seguridad que falla
        When: Se vincula
        Then: El vínculo sale bien igual (G1: el log nunca cambia la respuesta)
        """
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info
        auditoria.log_google_account_linked.side_effect = RuntimeError("log caído")

        respuesta = await use_case.execute(
            LinkGoogleAccountRequestDTO(authorization_code="code"), str(existing_user.id.value)
        )

        assert respuesta.provider_email == "link@gmail.com"
