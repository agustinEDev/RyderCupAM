"""
Tests para LoginUserUseCase

Tests unitarios para el caso de uso de login de usuario.
"""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from src.modules.user.application.dto.user_dto import LoginRequestDTO, LoginResponseDTO
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.exceptions import AccountDeactivatedException
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.shared.infrastructure.security.jwt_handler import JWTTokenService


def _rebuild_user(user: User, **overrides) -> User:
    """
    Reconstruye un User con los mismos valores, sobrescribiendo los indicados.

    Tras la encapsulación de User (issue #109), sus atributos son de solo
    lectura vía @property. Los tests que necesitan simular un estado concreto
    (p.ej. un handicap desactualizado) reconstruyen la entidad en vez de mutar
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
        "is_active": user.is_active,
        "gender": user.gender,
        "domain_events": user.get_domain_events(),
    }
    fields.update(overrides)
    return User(**fields)


@pytest.fixture
def uow():
    """Fixture que proporciona un Unit of Work en memoria."""
    return InMemoryUnitOfWork()


@pytest.fixture
def token_service():
    """Fixture que proporciona el servicio de tokens JWT."""
    return JWTTokenService()


@pytest.fixture
def register_device_use_case():
    """Fixture que proporciona un mock del RegisterDeviceUseCase (v1.13.0)."""
    mock = AsyncMock()
    mock.execute.return_value = AsyncMock()  # RegisterDeviceResponseDTO mock
    return mock


@pytest.fixture
async def existing_user(uow):
    """
    Fixture que crea un usuario existente en el sistema.
    Email: test@example.com
    Password: ValidPass123
    """
    user = User.create(
        first_name="John",
        last_name="Doe",
        email_str="test@example.com",
        plain_password="V@l1dP@ss123!",
    )

    async with uow:
        await uow.users.save(user)
        await uow.commit()

    return user


@pytest.mark.asyncio
class TestLoginUserUseCase:
    """Tests para el caso de uso de login."""

    async def test_login_successful_with_correct_credentials(
        self, uow, token_service, register_device_use_case, existing_user
    ):
        """Debe retornar token JWT cuando las credenciales son correctas."""
        # Arrange
        use_case = LoginUserUseCase(uow, token_service, register_device_use_case)
        request = LoginRequestDTO(email="test@example.com", password="V@l1dP@ss123!")

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is not None
        assert response.access_token is not None
        assert len(response.access_token) > 0
        assert response.token_type == "bearer"
        assert response.user.email == "test@example.com"
        assert response.user.first_name == "John"
        assert response.user.last_name == "Doe"
        assert response.user.id == existing_user.id.value

    async def test_login_fails_with_wrong_password(
        self, uow, token_service, register_device_use_case, existing_user
    ):
        """Debe retornar None cuando la contraseña es incorrecta."""
        # Arrange
        use_case = LoginUserUseCase(uow, token_service, register_device_use_case)
        request = LoginRequestDTO(email="test@example.com", password="Wr0ngP@ssw0rd!")

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is None

    async def test_login_fails_with_non_existent_email(
        self, uow, token_service, register_device_use_case
    ):
        """Debe retornar None cuando el email no existe."""
        # Arrange
        use_case = LoginUserUseCase(uow, token_service, register_device_use_case)
        request = LoginRequestDTO(email="nonexistent@example.com", password="S0m3P@ssw0rd!")

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is None

    async def test_login_response_does_not_include_password(
        self, uow, token_service, register_device_use_case, existing_user
    ):
        """Debe asegurarse que la respuesta NO incluye la contraseña."""
        # Arrange
        use_case = LoginUserUseCase(uow, token_service, register_device_use_case)
        request = LoginRequestDTO(email="test@example.com", password="V@l1dP@ss123!")

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is not None
        response_dict = response.model_dump()
        assert "password" not in response_dict["user"]

    async def test_login_token_contains_user_id_in_subject(
        self, uow, token_service, register_device_use_case, existing_user
    ):
        """Debe incluir el user_id en el subject del token."""
        # Arrange
        use_case = LoginUserUseCase(uow, token_service, register_device_use_case)
        request = LoginRequestDTO(email="test@example.com", password="V@l1dP@ss123!")

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is not None

        # Verificar que el token se puede decodificar
        from src.shared.infrastructure.security.jwt_handler import verify_access_token

        payload = verify_access_token(response.access_token)

        assert payload is not None
        assert "sub" in payload
        assert payload["sub"] == str(existing_user.id.value)
        assert "exp" in payload  # Debe tener tiempo de expiración

    async def test_registers_device_with_placeholder_ip_when_ip_unresolved(
        self, uow, token_service, register_device_use_case, existing_user
    ):
        """
        Debe seguir registrando el dispositivo (con IP placeholder) cuando
        ip_address es None pero hay user_agent.

        Antes de este fix, el registro de dispositivo (y por tanto la cookie
        device_id) se saltaba por completo si no había IP resuelta — lo que
        ocurre siempre que get_trusted_client_ip() rechaza el peer como
        sentinel (p.ej. 127.0.0.1 vía kubectl port-forward). Sin cookie
        device_id, ningún dispositivo se marca is_current_device=True y el
        frontend fuerza un logout inmediato interpretándolo como revocación.
        """
        from src.modules.user.application.dto.device_dto import UNRESOLVED_IP_PLACEHOLDER

        register_device_use_case.execute.return_value = AsyncMock(
            device_id="7c9e6679-7425-40de-944b-e07fc1f90ae7",
            set_device_cookie=True,
        )
        use_case = LoginUserUseCase(uow, token_service, register_device_use_case)
        request = LoginRequestDTO(
            email="test@example.com",
            password="V@l1dP@ss123!",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            ip_address=None,
        )

        response = await use_case.execute(request)

        assert response is not None
        register_device_use_case.execute.assert_awaited_once()
        call_kwargs = register_device_use_case.execute.call_args.args[0]
        assert call_kwargs.ip_address == UNRESOLVED_IP_PLACEHOLDER


@pytest.mark.asyncio
class TestLoginUserUseCaseNoEsperaALaRFEG:
    """
    El login ya no consulta la RFEG (RyderCupAM#340).

    La esperaba antes de contestar —hasta 20 s cuando la federación iba lenta— y
    el 21 sep 2026 tardó un minuto. El refresco vive ahora en
    RefreshOwnHandicapUseCase, que el frontend pide después de entrar; sus reglas
    se prueban en test_refresh_own_handicap_use_case.py.
    """

    async def test_login_de_un_espanol_con_el_handicap_de_ayer_no_lo_toca(
        self, token_service, register_device_use_case
    ):
        """L1: el caso que antes disparaba la RFEG entra sin cambiar el hándicap."""
        uow = InMemoryUnitOfWork()
        user = User.create(
            first_name="Juan",
            last_name="Garcia",
            email_str="es@example.com",
            plain_password="V@l1dP@ss123!",
            country_code_str="ES",
        )
        user.update_handicap(12.5)
        user = _rebuild_user(user, handicap_updated_at=user.handicap_updated_at - timedelta(days=1))
        async with uow:
            await uow.users.save(user)
            await uow.commit()

        use_case = LoginUserUseCase(uow, token_service, register_device_use_case)

        response = await use_case.execute(
            LoginRequestDTO(email="es@example.com", password="V@l1dP@ss123!")
        )

        assert response is not None
        assert response.user.handicap == 12.5

    def test_la_respuesta_del_login_ya_no_trae_needs_handicap(self):
        """
        L2: el campo se va del contrato.

        Es compatible con el frontend que hay en producción: lo lee con
        `data.needs_handicap || false`, así que su ausencia es un false.
        """
        assert "needs_handicap" not in LoginResponseDTO.model_fields


@pytest.mark.asyncio
class TestLoginUserUseCaseDeactivatedAccount:
    """
    Tests para el bloqueo de login en cuentas desactivadas (Admin Panel v2.4.0).

    La verificación de is_active ocurre DESPUÉS de validar la contraseña, para
    no filtrar el estado de la cuenta a quien no conoce las credenciales.
    """

    async def test_deactivated_account_with_correct_password_raises_exception(
        self, uow, token_service, register_device_use_case, existing_user
    ):
        """Contraseña correcta + cuenta desactivada → AccountDeactivatedException."""
        deactivated_user = _rebuild_user(existing_user, is_active=False)
        async with uow:
            await uow.users.save(deactivated_user)
            await uow.commit()

        use_case = LoginUserUseCase(uow, token_service, register_device_use_case)
        request = LoginRequestDTO(email="test@example.com", password="V@l1dP@ss123!")

        with pytest.raises(AccountDeactivatedException):
            await use_case.execute(request)

    async def test_deactivated_account_with_wrong_password_returns_none(
        self, uow, token_service, register_device_use_case, existing_user
    ):
        """
        Contraseña incorrecta + cuenta desactivada → None (no la excepción).

        Verifica el orden correcto: la contraseña se valida ANTES que el
        estado is_active, así que unas credenciales inválidas no revelan si
        la cuenta está o no desactivada.
        """
        deactivated_user = _rebuild_user(existing_user, is_active=False)
        async with uow:
            await uow.users.save(deactivated_user)
            await uow.commit()

        use_case = LoginUserUseCase(uow, token_service, register_device_use_case)
        request = LoginRequestDTO(email="test@example.com", password="Wr0ngP@ssw0rd!")

        response = await use_case.execute(request)

        assert response is None
