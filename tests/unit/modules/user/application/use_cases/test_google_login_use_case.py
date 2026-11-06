"""
Tests para GoogleLoginUseCase

Tests unitarios para el caso de uso de login/registro con Google OAuth.
Verifica los 3 flujos: OAuth existente, auto-link, auto-register.
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.modules.user.application.dto.device_dto import (
    UNKNOWN_USER_AGENT,
    RegisterDeviceResponseDTO,
)
from src.modules.user.application.dto.oauth_dto import GoogleLoginRequestDTO
from src.modules.user.application.ports.google_oauth_service_interface import (
    GoogleUserInfo,
)
from src.modules.user.application.use_cases.google_login_use_case import (
    GoogleEmailNotVerifiedError,
    GoogleLoginUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.shared.infrastructure.security.jwt_handler import JWTTokenService


def _rebuild_user(user: User, **overrides) -> User:
    """
    Reconstruye un User con los mismos valores, sobrescribiendo los indicados.

    Tras la encapsulación de User (issue #109), sus atributos son de solo
    lectura vía @property. Los tests que necesitan simular un estado concreto
    (p.ej. una cuenta ya bloqueada) reconstruyen la entidad en vez de mutar
    atributos directamente.
    """
    fields = {
        "id": user.id,
        "email": user.email,
        "password": user.password,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "handicap": user.handicap,
        "handicap_updated_at": user.handicap_updated_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "email_verified": user.email_verified,
        "verification_token": user.verification_token,
        "country_code": user.country_code,
        "password_reset_token": user.password_reset_token,
        "reset_token_expires_at": user.reset_token_expires_at,
        "failed_login_attempts": user.failed_login_attempts,
        "locked_until": user.locked_until,
        "is_admin": user.is_admin,
        "gender": user.gender,
        "domain_events": user.get_domain_events(),
    }
    fields.update(overrides)
    return User(**fields)


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def token_service():
    return JWTTokenService()


@pytest.fixture
def google_oauth_service():
    mock = AsyncMock()
    return mock


@pytest.fixture
def register_device_use_case():
    mock = AsyncMock()
    mock.execute.return_value = RegisterDeviceResponseDTO(
        device_id="550e8400-e29b-41d4-a716-446655440099",
        is_new_device=True,
        message="New device registered",
    )
    return mock


@pytest.fixture
def google_user_info():
    return GoogleUserInfo(
        google_user_id="google-id-12345",
        email="oauth@example.com",
        first_name="Google",
        last_name="User",
        email_verified=True,
        picture_url="https://lh3.googleusercontent.com/photo.jpg",
    )


@pytest.fixture
def use_case(uow, token_service, google_oauth_service, register_device_use_case):
    return GoogleLoginUseCase(
        uow=uow,
        token_service=token_service,
        google_oauth_service=google_oauth_service,
        register_device_use_case=register_device_use_case,
        aviso_de_nuevo_inicio=AsyncMock(),
    )


@pytest.fixture
def login_request():
    return GoogleLoginRequestDTO(
        authorization_code="valid-auth-code",
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0 Test",
        device_id_from_cookie=None,
    )


@pytest.mark.asyncio
class TestGoogleLoginUseCaseAutoRegister:
    """Tests para flujo 3: usuario nuevo → auto-register."""

    async def test_auto_register_creates_new_user(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """Debe crear usuario nuevo cuando no existe en el sistema."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        response = await use_case.execute(login_request)

        assert response is not None
        assert response.is_new_user is True
        assert response.user.email == "oauth@example.com"
        assert response.user.first_name == "Google"
        assert response.user.last_name == "User"
        assert response.token_type == "bearer"
        assert response.access_token is not None
        assert response.refresh_token is not None

    async def test_auto_register_user_has_no_password(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """El usuario creado desde OAuth no debe tener password."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(login_request)

        # Buscar usuario en el repo
        from src.modules.user.domain.value_objects.email import Email

        user = await uow.users.find_by_email(Email("oauth@example.com"))
        assert user is not None
        assert user.has_password is False

    async def test_auto_register_user_email_verified(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """El usuario OAuth debe tener email verificado."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(login_request)

        from src.modules.user.domain.value_objects.email import Email

        user = await uow.users.find_by_email(Email("oauth@example.com"))
        assert user is not None
        assert user.email_verified is True

    async def test_auto_register_creates_oauth_account(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """Debe crear OAuthAccount vinculado al nuevo usuario."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(login_request)

        oauth = await uow.oauth_accounts.find_by_provider_and_provider_user_id(
            OAuthProvider.GOOGLE, "google-id-12345"
        )
        assert oauth is not None
        assert oauth.provider_email == "oauth@example.com"

    async def test_auto_register_device_registration(
        self,
        use_case,
        google_oauth_service,
        google_user_info,
        login_request,
        register_device_use_case,
    ):
        """Debe registrar dispositivo y retornar device_id."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        response = await use_case.execute(login_request)

        assert response.device_id == "550e8400-e29b-41d4-a716-446655440099"
        register_device_use_case.execute.assert_called_once()


@pytest.mark.asyncio
class TestGoogleLoginUseCaseExistingOAuth:
    """Tests para flujo 1: OAuth account existente → login directo."""

    async def test_existing_oauth_user_login(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """Debe hacer login directo cuando ya existe OAuth account."""
        # Crear usuario y OAuth account existentes
        user = User.create_from_oauth(
            first_name="Existing",
            last_name="User",
            email_str="oauth@example.com",
        )
        async with uow:
            await uow.users.save(user)

        oauth_account = UserOAuthAccount.create(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-id-12345",
            provider_email="oauth@example.com",
        )
        async with uow:
            await uow.oauth_accounts.save(oauth_account)

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        response = await use_case.execute(login_request)

        assert response is not None
        assert response.is_new_user is False
        assert response.user.email == "oauth@example.com"
        assert response.user.first_name == "Existing"

    async def test_existing_oauth_user_not_found_raises(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """Debe lanzar error si OAuth account existe pero usuario no."""
        # Crear solo OAuth account sin usuario
        fake_user_id = UserId.generate()
        oauth_account = UserOAuthAccount.create(
            user_id=fake_user_id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-id-12345",
            provider_email="orphan@example.com",
        )
        async with uow:
            await uow.oauth_accounts.save(oauth_account)

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        with pytest.raises(ValueError, match="User associated with OAuth account not found"):
            await use_case.execute(login_request)


@pytest.mark.asyncio
class TestGoogleLoginUseCaseAutoLink:
    """Tests para flujo 2: usuario email existente → auto-link."""

    async def test_auto_link_existing_email_user(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """Debe auto-link cuando usuario existe por email pero sin OAuth."""
        user = User.create(
            first_name="Email",
            last_name="User",
            email_str="oauth@example.com",
            plain_password="V@l1dP@ss123!",
        )
        async with uow:
            await uow.users.save(user)

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        response = await use_case.execute(login_request)

        assert response.is_new_user is False
        assert response.user.first_name == "Email"

        # Verificar que se creó la OAuth account
        oauth = await uow.oauth_accounts.find_by_provider_and_provider_user_id(
            OAuthProvider.GOOGLE, "google-id-12345"
        )
        assert oauth is not None

    async def test_auto_link_verifies_unverified_email(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """Debe verificar email si el usuario existente no lo tiene verificado."""
        user = User.create(
            first_name="Unverified",
            last_name="User",
            email_str="oauth@example.com",
            plain_password="V@l1dP@ss123!",
        )
        assert user.email_verified is False
        async with uow:
            await uow.users.save(user)

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(login_request)

        # Verificar que ahora tiene email verificado
        from src.modules.user.domain.value_objects.email import Email

        updated_user = await uow.users.find_by_email(Email("oauth@example.com"))
        assert updated_user.email_verified is True


@pytest.mark.asyncio
class TestGoogleLoginUseCaseLockout:
    """Tests para protección de cuenta bloqueada."""

    async def test_a_tripped_backstop_does_not_stop_google_sign_in(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """
        Given: El respaldo de la cuenta bloqueado por fallos de contraseña (BE #732)
        When: Entra con Google
        Then: Entra, y el respaldo sigue igual: Google ya demuestra que es él, y una
              cuenta solo de Google no tiene contraseña buena con la que defenderse
        """
        user = User.create_from_oauth(
            first_name="Locked",
            last_name="User",
            email_str="oauth@example.com",
        )
        # Bloquear la cuenta
        from datetime import timedelta

        user = _rebuild_user(
            user,
            locked_until=datetime.now() + timedelta(minutes=30),
            failed_login_attempts=10,
        )

        async with uow:
            await uow.users.save(user)

        oauth_account = UserOAuthAccount.create(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-id-12345",
            provider_email="oauth@example.com",
        )
        async with uow:
            await uow.oauth_accounts.save(oauth_account)

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        respuesta = await use_case.execute(login_request)

        assert respuesta.access_token
        async with uow:
            guardado = await uow.users.find_by_id(user.id)
        assert guardado.failed_login_attempts == 10
        assert guardado.locked_until is not None


@pytest.mark.asyncio
class TestGoogleLoginUseCaseTokenGeneration:
    """Tests para generación de tokens."""

    async def test_generates_access_and_refresh_tokens(
        self, use_case, google_oauth_service, google_user_info, login_request
    ):
        """Debe generar tokens JWT válidos."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        response = await use_case.execute(login_request)

        assert len(response.access_token) > 0
        assert len(response.refresh_token) > 0
        assert response.csrf_token is not None
        assert len(response.csrf_token) > 0

    async def test_invalid_code_raises_value_error(
        self, use_case, google_oauth_service, login_request
    ):
        """Debe propagar ValueError cuando el código es inválido."""
        google_oauth_service.exchange_code_for_user_info.side_effect = ValueError(
            "Invalid or expired Google authorization code"
        )

        with pytest.raises(ValueError, match="Invalid or expired"):
            await use_case.execute(login_request)

    async def test_registers_a_device_even_without_user_agent(
        self, use_case, uow, google_oauth_service, google_user_info, register_device_use_case
    ):
        """
        Given: Un login con Google sin User-Agent
        When: Se ejecuta
        Then: Registra igualmente un dispositivo, con el agente desconocido: una sesión
              sin dispositivo no salía en la lista ni se podía revocar (auditoría OWASP, A07)
        """
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        request = GoogleLoginRequestDTO(
            authorization_code="valid-code",
            ip_address=None,
            user_agent=None,
        )

        response = await use_case.execute(request)

        assert response.device_id is not None
        enviado = register_device_use_case.execute.await_args.args[0]
        assert enviado.user_agent == UNKNOWN_USER_AGENT

    async def test_registers_device_with_placeholder_ip_when_ip_unresolved(
        self, use_case, google_oauth_service, google_user_info, register_device_use_case
    ):
        """
        Debe seguir registrando el dispositivo (con IP placeholder) cuando
        ip_address es None pero hay user_agent — ver test equivalente en
        test_login_user_use_case.py para el porqué (device_id cookie nunca se
        fijaba, causando logout inmediato por falsa revocación).
        """
        from src.modules.user.application.dto.device_dto import UNRESOLVED_IP_PLACEHOLDER

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        request = GoogleLoginRequestDTO(
            authorization_code="valid-code",
            ip_address=None,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        )

        await use_case.execute(request)
        register_device_use_case.execute.assert_awaited_once()
        call_kwargs = register_device_use_case.execute.call_args.args[0]
        assert call_kwargs.ip_address == UNRESOLVED_IP_PLACEHOLDER


@pytest.mark.asyncio
class TestGoogleLoginNuevoInicio:
    """El aviso de nuevo inicio de sesión con Google (BE #737)."""

    async def test_sign_up_with_google_tells_the_notice_it_is_the_sign_up(
        self,
        uow,
        token_service,
        google_oauth_service,
        register_device_use_case,
        google_user_info,
        login_request,
    ):
        """
        Given: Alguien sin cuenta que entra con Google
        When: Se crea la cuenta
        Then: Se le dice al aviso que es el alta (no avisa), con el correo confirmado
        """
        aviso = AsyncMock()
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info
        use_case = GoogleLoginUseCase(
            uow=uow,
            token_service=token_service,
            google_oauth_service=google_oauth_service,
            register_device_use_case=register_device_use_case,
            aviso_de_nuevo_inicio=aviso,
        )

        await use_case.execute(login_request)

        enviado = aviso.avisa.await_args.args[0]
        assert enviado.es_alta is True
        assert enviado.verificado is True

    async def test_the_notice_goes_to_the_account_email_not_the_google_one(
        self,
        uow,
        token_service,
        google_oauth_service,
        register_device_use_case,
        google_user_info,
        login_request,
    ):
        """
        Given: Una cuenta con su correo, vinculada a una cuenta de Google con otra dirección
        When: Entra con Google
        Then: El aviso va al correo de la cuenta: si lo comprometido es la cuenta de Google,
              el aviso no puede llegar a quien la controla (auditoría OWASP, 5 nov 2026)
        """
        user = User.create_from_oauth(
            first_name="Ana", last_name="Golf", email_str="ana@example.com"
        )
        async with uow:
            await uow.users.save(user)
            await uow.oauth_accounts.save(
                UserOAuthAccount.create(
                    user_id=user.id,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id="google-id-12345",
                    provider_email="oauth@example.com",
                )
            )
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info
        aviso = AsyncMock()
        use_case = GoogleLoginUseCase(
            uow=uow,
            token_service=token_service,
            google_oauth_service=google_oauth_service,
            register_device_use_case=register_device_use_case,
            aviso_de_nuevo_inicio=aviso,
        )

        await use_case.execute(login_request)

        enviado = aviso.avisa.await_args.args[0]
        assert enviado.email == "ana@example.com"
        assert enviado.es_alta is False

    @pytest.mark.parametrize(("por_su_cookie", "desconocido"), [(False, True), (True, False)])
    async def test_a_known_device_without_its_cookie_is_notified(
        self,
        uow,
        token_service,
        google_oauth_service,
        google_user_info,
        login_request,
        por_su_cookie,
        desconocido,
    ):
        """
        Given: Un dispositivo ya conocido, que llega sin su cookie (solo la huella) o con ella
        When: Entra con Google
        Then: Sin su cookie se avisa; con ella, no (decidido el 6 nov 2026)
        """
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info
        registro = AsyncMock()
        registro.execute.return_value = RegisterDeviceResponseDTO(
            device_id="550e8400-e29b-41d4-a716-446655440099",
            is_new_device=False,
            message="Dispositivo actualizado",
            recognized_by_cookie=por_su_cookie,
        )
        aviso = AsyncMock()
        use_case = GoogleLoginUseCase(
            uow=uow,
            token_service=token_service,
            google_oauth_service=google_oauth_service,
            register_device_use_case=registro,
            aviso_de_nuevo_inicio=aviso,
        )

        await use_case.execute(login_request)

        assert aviso.avisa.await_args.args[0].desconocido is desconocido


@pytest.mark.asyncio
class TestGoogleLoginCuentaDesactivada:
    """Una cuenta desactivada no entra con Google (BE #744, auditoría OWASP)."""

    async def test_a_deactivated_account_gets_no_session_device_or_email(
        self, uow, token_service, google_oauth_service, google_user_info, register_device_use_case
    ):
        """
        Given: Una cuenta vinculada a Google, desactivada por un administrador
        When: Entra con Google
        Then: AccountDeactivatedException, y ni dispositivo, ni token, ni correo
        """
        from src.modules.user.domain.exceptions import AccountDeactivatedException

        user = User.create_from_oauth(
            first_name="Baja", last_name="Google", email_str="oauth@example.com"
        )
        user.deactivate(deactivated_by_user_id="5f0c8a2e-1b3d-4e6f-9a7b-2c4d6e8f0a1b")
        async with uow:
            await uow.users.save(user)
            await uow.oauth_accounts.save(
                UserOAuthAccount.create(
                    user_id=user.id,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id="google-id-12345",
                    provider_email="oauth@example.com",
                )
            )
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info
        aviso = AsyncMock()
        caso = GoogleLoginUseCase(
            uow=uow,
            token_service=token_service,
            google_oauth_service=google_oauth_service,
            register_device_use_case=register_device_use_case,
            aviso_de_nuevo_inicio=aviso,
        )

        with pytest.raises(AccountDeactivatedException):
            await caso.execute(
                GoogleLoginRequestDTO(authorization_code="code", ip_address="203.0.113.7")
            )

        register_device_use_case.execute.assert_not_awaited()
        aviso.avisa.assert_not_awaited()
        async with uow:
            assert await uow.refresh_tokens.find_all_by_user(user.id) == []

    async def test_a_deactivated_account_found_by_email_is_not_linked_to_google(
        self, uow, token_service, google_oauth_service, google_user_info, register_device_use_case
    ):
        """
        Given: Una cuenta desactivada, sin vincular a Google, con el correo sin verificar
        When: Alguien entra con un Google que tiene ese correo
        Then: 403, y la cuenta queda como estaba: sin vínculo y sin verificar
        """
        from src.modules.user.domain.exceptions import AccountDeactivatedException

        user = User.create(
            first_name="Baja",
            last_name="Correo",
            email_str="oauth@example.com",
            plain_password="SecureP@ssw0rd123!",
        )
        user.deactivate(deactivated_by_user_id="5f0c8a2e-1b3d-4e6f-9a7b-2c4d6e8f0a1b")
        async with uow:
            await uow.users.save(user)
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info
        caso = GoogleLoginUseCase(
            uow=uow,
            token_service=token_service,
            google_oauth_service=google_oauth_service,
            register_device_use_case=register_device_use_case,
            aviso_de_nuevo_inicio=AsyncMock(),
        )

        with pytest.raises(AccountDeactivatedException):
            await caso.execute(GoogleLoginRequestDTO(authorization_code="code"))

        async with uow:
            assert (
                await uow.oauth_accounts.find_by_provider_and_provider_user_id(
                    OAuthProvider.GOOGLE, google_user_info.google_user_id
                )
                is None
            )
            assert not (await uow.users.find_by_id(user.id)).email_verified


def _sin_verificar(info: GoogleUserInfo) -> GoogleUserInfo:
    return GoogleUserInfo(
        google_user_id=info.google_user_id,
        email=info.email,
        first_name=info.first_name,
        last_name=info.last_name,
        email_verified=False,
        picture_url=info.picture_url,
    )


@pytest.mark.asyncio
class TestGoogleConElCorreoSinVerificar:
    """Sin el correo verificado por Google, ni alta ni vínculo (revisión del registro)."""

    async def test_it_does_not_link_an_existing_account(
        self, use_case, uow, google_oauth_service, google_user_info
    ):
        """
        Given: Una cuenta con contraseña y el correo oauth@example.com
        When: Alguien entra con un Google de ese correo, SIN verificar por Google
        Then: GoogleEmailNotVerifiedError y ningún vínculo: si no, cualquiera con una
              cuenta de Google con tu dirección entraría en la tuya
        """
        cuenta = User.create(
            first_name="Ana",
            last_name="Dueña",
            email_str="oauth@example.com",
            plain_password="SecureP@ssw0rd123!",
        )
        async with uow:
            await uow.users.save(cuenta)
        google_oauth_service.exchange_code_for_user_info.return_value = _sin_verificar(
            google_user_info
        )

        with pytest.raises(GoogleEmailNotVerifiedError):
            await use_case.execute(GoogleLoginRequestDTO(authorization_code="code"))

        async with uow:
            assert (
                await uow.oauth_accounts.find_by_provider_and_provider_user_id(
                    OAuthProvider.GOOGLE, google_user_info.google_user_id
                )
                is None
            )

    async def test_it_does_not_sign_up(self, use_case, uow, google_oauth_service, google_user_info):
        """
        Given: Ningún usuario con ese correo
        When: Alguien se da de alta con un Google SIN el correo verificado
        Then: GoogleEmailNotVerifiedError y ninguna cuenta creada: no se ocupa el
              correo de otro
        """
        google_oauth_service.exchange_code_for_user_info.return_value = _sin_verificar(
            google_user_info
        )

        with pytest.raises(GoogleEmailNotVerifiedError):
            await use_case.execute(GoogleLoginRequestDTO(authorization_code="code"))

        async with uow:
            assert await uow.users.find_by_email(Email("oauth@example.com")) is None

    async def test_an_already_linked_google_still_signs_in(
        self, use_case, uow, google_oauth_service, google_user_info
    ):
        """
        Given: Un Google ya vinculado a su cuenta (Google lo verificó al vincularlo)
        When: Entra y Google ahora dice que el correo no está verificado
        Then: Entra: la cuenta ya es suya, por su id de Google
        """
        cuenta = User.create_from_oauth(
            first_name="Ana", last_name="Vinculada", email_str="oauth@example.com"
        )
        async with uow:
            await uow.users.save(cuenta)
            await uow.oauth_accounts.save(
                UserOAuthAccount.create(
                    user_id=cuenta.id,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id=google_user_info.google_user_id,
                    provider_email="oauth@example.com",
                )
            )
        google_oauth_service.exchange_code_for_user_info.return_value = _sin_verificar(
            google_user_info
        )

        respuesta = await use_case.execute(GoogleLoginRequestDTO(authorization_code="code"))

        assert respuesta.user.email == "oauth@example.com"


@pytest.mark.asyncio
class TestElVinculoAutomaticoAlLog:
    """El vínculo automático va al log después de guardar, con la red, sin romper nada."""

    async def _cuenta(self, uow):
        cuenta = User.create(
            first_name="Ana",
            last_name="Dueña",
            email_str="oauth@example.com",
            plain_password="SecureP@ssw0rd123!",
        )
        async with uow:
            await uow.users.save(cuenta)
        return cuenta

    async def test_it_logs_the_link_with_the_network(
        self, use_case, uow, google_oauth_service, google_user_info, monkeypatch
    ):
        """
        Given: Una cuenta con el correo de un Google verificado, sin vincular
        When: Entra con ese Google desde una IP y un navegador
        Then: El log de seguridad apunta el vínculo automático con esa IP y ese navegador
        """
        from src.shared.infrastructure.logging import security_logger as modulo

        apuntes = []
        monkeypatch.setattr(
            modulo.SecurityLogger,
            "log_google_account_linked",
            lambda self, **kw: apuntes.append(kw),
        )
        cuenta = await self._cuenta(uow)
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(
            GoogleLoginRequestDTO(
                authorization_code="code", ip_address="203.0.113.7", user_agent="Navegador"
            )
        )

        assert apuntes == [
            {
                "user_id": str(cuenta.id.value),
                "automatic": True,
                "ip_address": "203.0.113.7",
                "user_agent": "Navegador",
            }
        ]

    async def test_a_broken_log_does_not_undo_the_link_nor_the_login(
        self, use_case, uow, google_oauth_service, google_user_info, monkeypatch
    ):
        """
        Given: El log de seguridad falla
        When: Alguien entra con un Google que se vincula solo
        Then: Entra y el vínculo queda guardado: el log nunca cambia la respuesta
        """
        from src.shared.infrastructure.logging import security_logger as modulo

        def roto(self, **kw):
            raise RuntimeError("disco lleno")

        monkeypatch.setattr(modulo.SecurityLogger, "log_google_account_linked", roto)
        await self._cuenta(uow)
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        respuesta = await use_case.execute(GoogleLoginRequestDTO(authorization_code="code"))

        assert respuesta.user.email == "oauth@example.com"
        async with uow:
            assert await uow.oauth_accounts.find_by_provider_and_provider_user_id(
                OAuthProvider.GOOGLE, google_user_info.google_user_id
            )


@pytest.mark.asyncio
class TestGoogleSeQuedaUnaCuentaSinVerificar:
    """Pre-captura: la cuenta sin verificar con ese correo la pudo crear cualquiera (G1-G7)."""

    async def _cuenta_con_sesion(self, uow, verificada: bool):
        from src.modules.user.domain.entities.refresh_token import RefreshToken
        from src.modules.user.domain.entities.user_device import UserDevice
        from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint

        cuenta = User.create(
            first_name="Ana",
            last_name="Dueña",
            email_str="oauth@example.com",
            plain_password="SecureP@ssw0rd123!",
        )
        if verificada:
            cuenta.confirm_email_ownership()
        dispositivo = UserDevice.create(
            user_id=cuenta.id,
            fingerprint=DeviceFingerprint.create(
                "Mozilla/5.0 (X11; Linux x86_64) Firefox/131.0", "198.51.100.9"
            ),
        )
        token = RefreshToken.create(
            user_id=cuenta.id,
            token="refresco-del-otro",
            device_id=dispositivo.id,
            expires_in_days=7,
        )
        async with uow:
            await uow.users.save(cuenta)
            await uow.user_devices.save(dispositivo)
            await uow.refresh_tokens.save(token)
        return cuenta, dispositivo

    async def test_g1_google_claims_it_and_drops_what_was_never_proven(
        self, use_case, uow, google_oauth_service, google_user_info
    ):
        """
        Given: Una cuenta sin verificar, con contraseña, un dispositivo y una sesión
        When: Entra un Google que verificó ese correo
        Then: Se vincula y se verifica; sin contraseña; el dispositivo y la sesión
              de antes, revocados (los de quien la creó)
        """
        cuenta, dispositivo = await self._cuenta_con_sesion(uow, verificada=False)
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(GoogleLoginRequestDTO(authorization_code="code"))

        async with uow:
            guardada = await uow.users.find_by_id(cuenta.id)
            assert guardada.email_verified
            assert not guardada.has_password
            assert await uow.oauth_accounts.find_by_provider_and_provider_user_id(
                OAuthProvider.GOOGLE, google_user_info.google_user_id
            )
            assert not (await uow.user_devices.find_by_id(dispositivo.id)).is_active
            assert (await uow.refresh_tokens.find_by_token_hash("refresco-del-otro")).revoked

    async def test_g1_the_new_google_session_stays_open(
        self, use_case, uow, google_oauth_service, google_user_info
    ):
        """
        Given: La misma cuenta sin verificar
        When: Entra con Google
        Then: El refresh token de ESTE login sigue vivo: solo se cierra lo de antes
        """
        _cuenta, _d = await self._cuenta_con_sesion(uow, verificada=False)
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        respuesta = await use_case.execute(GoogleLoginRequestDTO(authorization_code="code"))

        async with uow:
            nuevo = await uow.refresh_tokens.find_by_token_hash(respuesta.refresh_token)
            assert nuevo is not None and not nuevo.revoked

    async def test_g3_a_verified_account_keeps_its_password_and_sessions(
        self, use_case, uow, google_oauth_service, google_user_info
    ):
        """
        Given: Una cuenta YA verificada, con contraseña y sesión
        When: Entra con Google
        Then: Se vincula como siempre: conserva la contraseña, el dispositivo y la sesión
        """
        cuenta, dispositivo = await self._cuenta_con_sesion(uow, verificada=True)
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(GoogleLoginRequestDTO(authorization_code="code"))

        async with uow:
            assert (await uow.users.find_by_id(cuenta.id)).has_password
            assert (await uow.user_devices.find_by_id(dispositivo.id)).is_active
            assert not (await uow.refresh_tokens.find_by_token_hash("refresco-del-otro")).revoked

    async def test_g7_the_claim_goes_to_the_security_log(
        self, use_case, uow, google_oauth_service, google_user_info, monkeypatch
    ):
        """
        Given: La cuenta sin verificar con un dispositivo y una sesión
        When: Entra con Google desde una IP y un navegador
        Then: El log apunta la toma con lo que se cerró, la IP y el navegador
        """
        from src.shared.infrastructure.logging import security_logger as modulo

        apuntes = []
        monkeypatch.setattr(
            modulo.SecurityLogger,
            "log_unverified_account_claimed",
            lambda self, **kw: apuntes.append(kw),
            raising=False,
        )
        cuenta, _d = await self._cuenta_con_sesion(uow, verificada=False)
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(
            GoogleLoginRequestDTO(
                authorization_code="code", ip_address="203.0.113.7", user_agent="Navegador"
            )
        )

        assert apuntes == [
            {
                "user_id": str(cuenta.id.value),
                "devices_revoked": 1,
                "tokens_revoked": 1,
                "google_unlinked": 0,
                "ip_address": "203.0.113.7",
                "user_agent": "Navegador",
            }
        ]

    async def test_g7_a_broken_log_does_not_change_the_login(
        self, use_case, uow, google_oauth_service, google_user_info, monkeypatch
    ):
        """
        Given: El log de seguridad falla
        When: Google se queda la cuenta sin verificar
        Then: Entra igual, y la cuenta queda tomada
        """
        from src.shared.infrastructure.logging import security_logger as modulo

        def roto(self, **kw):
            raise RuntimeError("disco lleno")

        monkeypatch.setattr(
            modulo.SecurityLogger, "log_unverified_account_claimed", roto, raising=False
        )
        cuenta, _d = await self._cuenta_con_sesion(uow, verificada=False)
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        respuesta = await use_case.execute(GoogleLoginRequestDTO(authorization_code="code"))

        assert respuesta.user.email == "oauth@example.com"
        async with uow:
            assert not (await uow.users.find_by_id(cuenta.id)).has_password

    async def test_g1_a_google_the_creator_linked_is_removed(
        self, use_case, uow, google_oauth_service, google_user_info, monkeypatch
    ):
        """
        Given: La cuenta sin verificar, con OTRO Google vinculado por quien la creó
        When: Entra el Google que verificó el correo
        Then: Se queda solo el suyo: el otro se quita (tampoco se probó) y va al log
        """
        from src.shared.infrastructure.logging import security_logger as modulo

        apuntes = []
        monkeypatch.setattr(
            modulo.SecurityLogger,
            "log_unverified_account_claimed",
            lambda self, **kw: apuntes.append(kw),
        )
        cuenta, _d = await self._cuenta_con_sesion(uow, verificada=False)
        async with uow:
            await uow.oauth_accounts.save(
                UserOAuthAccount.create(
                    user_id=cuenta.id,
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id="google-del-atacante",
                    provider_email="atacante@example.com",
                )
            )
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(GoogleLoginRequestDTO(authorization_code="code"))

        async with uow:
            assert (
                await uow.oauth_accounts.find_by_provider_and_provider_user_id(
                    OAuthProvider.GOOGLE, "google-del-atacante"
                )
                is None
            )
            suyo = await uow.oauth_accounts.find_by_user_id_and_provider(
                cuenta.id, OAuthProvider.GOOGLE
            )
            assert suyo.provider_user_id == google_user_info.google_user_id
        assert apuntes[0]["google_unlinked"] == 1

    async def test_g3_a_verified_account_is_not_logged_as_claimed(
        self, use_case, uow, google_oauth_service, google_user_info, monkeypatch
    ):
        """Una verificada se vincula sin apuntar ninguna toma."""
        from src.shared.infrastructure.logging import security_logger as modulo

        apuntes = []
        monkeypatch.setattr(
            modulo.SecurityLogger,
            "log_unverified_account_claimed",
            lambda self, **kw: apuntes.append(kw),
        )
        await self._cuenta_con_sesion(uow, verificada=True)
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(GoogleLoginRequestDTO(authorization_code="code"))

        assert apuntes == []

    async def test_g4_a_deactivated_unverified_account_is_not_claimed(
        self, use_case, uow, google_oauth_service, google_user_info
    ):
        """
        Given: La cuenta sin verificar, desactivada por un administrador
        When: Entra con Google
        Then: 403, y conserva contraseña y sesiones: un login rechazado no cambia nada
        """
        from src.modules.user.domain.exceptions import AccountDeactivatedException

        cuenta, dispositivo = await self._cuenta_con_sesion(uow, verificada=False)
        cuenta.deactivate(deactivated_by_user_id="5f0c8a2e-1b3d-4e6f-9a7b-2c4d6e8f0a1b")
        async with uow:
            await uow.users.save(cuenta)
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        with pytest.raises(AccountDeactivatedException):
            await use_case.execute(GoogleLoginRequestDTO(authorization_code="code"))

        async with uow:
            assert (await uow.users.find_by_id(cuenta.id)).has_password
            assert (await uow.user_devices.find_by_id(dispositivo.id)).is_active

    async def test_g8_the_claim_reads_the_account_with_the_row_locked(
        self, use_case, uow, google_oauth_service, google_user_info
    ):
        """
        Given: La cuenta sin verificar
        When: Google se la queda
        Then: La relee con la fila bloqueada: un login con contraseña a la vez espera
        """
        cuenta, _d = await self._cuenta_con_sesion(uow, verificada=False)
        pedidos = []
        original = uow.users.find_by_id_for_update

        async def espia(user_id):
            pedidos.append(user_id)
            return await original(user_id)

        uow.users.find_by_id_for_update = espia
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(GoogleLoginRequestDTO(authorization_code="code"))

        assert pedidos == [cuenta.id]

    async def test_g9_deactivated_right_before_the_lock_is_not_claimed(
        self, use_case, uow, google_oauth_service, google_user_info
    ):
        """
        Given: La cuenta sin verificar, que un administrador desactiva justo antes de
               que Google la bloquee
        When: Google iba a quedársela
        Then: 403 y la cuenta como estaba: un login rechazado no cambia la cuenta
        """
        import copy

        from src.modules.user.domain.exceptions import AccountDeactivatedException

        cuenta, dispositivo = await self._cuenta_con_sesion(uow, verificada=False)

        async def desactivada(user_id):
            otra = copy.deepcopy(uow.users._users[user_id])
            otra.deactivate(deactivated_by_user_id="5f0c8a2e-1b3d-4e6f-9a7b-2c4d6e8f0a1b")
            uow.users._users[user_id] = otra
            return otra

        uow.users.find_by_id_for_update = desactivada
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        with pytest.raises(AccountDeactivatedException):
            await use_case.execute(GoogleLoginRequestDTO(authorization_code="code"))

        async with uow:
            assert (await uow.users.find_by_id(cuenta.id)).has_password
            assert (await uow.user_devices.find_by_id(dispositivo.id)).is_active

    async def test_g10_an_email_changed_right_before_the_lock_is_not_claimed(
        self, use_case, uow, google_oauth_service, google_user_info
    ):
        """
        Given: La cuenta sin verificar con el correo de Google, que cambia de correo justo
               antes de que Google la bloquee
        When: Google iba a quedársela
        Then: No se la queda (ya no es la cuenta de ese correo): error, y conserva la
              contraseña
        """
        import copy

        cuenta, _d = await self._cuenta_con_sesion(uow, verificada=False)

        async def otro_correo(user_id):
            otra = copy.deepcopy(uow.users._users[user_id])
            otra.change_email("otro.correo@example.com")
            uow.users._users[user_id] = otra
            return otra

        uow.users.find_by_id_for_update = otro_correo
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        with pytest.raises(ValueError):
            await use_case.execute(GoogleLoginRequestDTO(authorization_code="code"))

        async with uow:
            assert (await uow.users.find_by_id(cuenta.id)).has_password
