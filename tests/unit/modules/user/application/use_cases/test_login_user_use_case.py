"""
Tests para LoginUserUseCase

Tests unitarios para el caso de uso de login de usuario.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.user.application.dto.user_dto import LoginRequestDTO
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.handicap_errors import HandicapServiceUnavailableError
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.shared.infrastructure.security.jwt_handler import JWTTokenService


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


@pytest.mark.asyncio
class TestLoginUserUseCaseHandicapRFEG:
    """Tests para el fetch de hándicap RFEG en login (HM-2a)."""

    def _make_use_case(self, uow, token_service, register_device_use_case, handicap_service=None):
        return LoginUserUseCase(uow, token_service, register_device_use_case, handicap_service)

    def _make_handicap_service(self, return_value=None, raise_exc=None):
        svc = MagicMock()
        if raise_exc:
            svc.search_handicap = AsyncMock(side_effect=raise_exc)
        else:
            svc.search_handicap = AsyncMock(return_value=return_value)
        return svc

    async def _create_es_user(self, uow, email="es@example.com"):
        user = User.create(
            first_name="Juan",
            last_name="Garcia",
            email_str=email,
            plain_password="V@l1dP@ss123!",
            country_code_str="ES",
        )
        async with uow:
            await uow.users.save(user)
            await uow.commit()
        return user

    async def test_es_user_no_handicap_rfeg_returns_value_updates_and_needs_handicap_false(
        self, token_service, register_device_use_case
    ):
        """ES sin hándicap + RFEG devuelve valor → actualiza handicap, needs_handicap=False."""
        uow = InMemoryUnitOfWork()
        await self._create_es_user(uow)
        handicap_svc = self._make_handicap_service(return_value=18.4)
        use_case = self._make_use_case(uow, token_service, register_device_use_case, handicap_svc)

        response = await use_case.execute(
            LoginRequestDTO(email="es@example.com", password="V@l1dP@ss123!")
        )

        assert response is not None
        assert response.needs_handicap is False
        assert response.user.handicap == 18.4
        handicap_svc.search_handicap.assert_awaited_once_with("Juan Garcia")

    async def test_es_user_no_handicap_rfeg_returns_none_needs_handicap_true(
        self, token_service, register_device_use_case
    ):
        """ES sin hándicap + RFEG devuelve None → needs_handicap=True."""
        uow = InMemoryUnitOfWork()
        await self._create_es_user(uow)
        handicap_svc = self._make_handicap_service(return_value=None)
        use_case = self._make_use_case(uow, token_service, register_device_use_case, handicap_svc)

        response = await use_case.execute(
            LoginRequestDTO(email="es@example.com", password="V@l1dP@ss123!")
        )

        assert response is not None
        assert response.needs_handicap is True

    async def test_es_user_no_handicap_rfeg_fails_needs_handicap_true(
        self, token_service, register_device_use_case
    ):
        """ES sin hándicap + RFEG lanza excepción → login OK, needs_handicap=True (soft fail)."""
        uow = InMemoryUnitOfWork()
        await self._create_es_user(uow)
        handicap_svc = self._make_handicap_service(
            raise_exc=HandicapServiceUnavailableError("RFEG down")
        )
        use_case = self._make_use_case(uow, token_service, register_device_use_case, handicap_svc)

        response = await use_case.execute(
            LoginRequestDTO(email="es@example.com", password="V@l1dP@ss123!")
        )

        assert response is not None
        assert response.needs_handicap is True

    async def test_es_user_with_existing_handicap_no_rfeg_call(
        self, token_service, register_device_use_case
    ):
        """ES con hándicap ya registrado → no llama RFEG, needs_handicap=False."""
        uow = InMemoryUnitOfWork()
        user = User.create(
            first_name="Juan",
            last_name="Garcia",
            email_str="es2@example.com",
            plain_password="V@l1dP@ss123!",
            country_code_str="ES",
        )
        user.update_handicap(12.5)
        async with uow:
            await uow.users.save(user)
            await uow.commit()

        handicap_svc = self._make_handicap_service(return_value=15.0)
        use_case = self._make_use_case(uow, token_service, register_device_use_case, handicap_svc)

        response = await use_case.execute(
            LoginRequestDTO(email="es2@example.com", password="V@l1dP@ss123!")
        )

        assert response is not None
        assert response.needs_handicap is False
        handicap_svc.search_handicap.assert_not_awaited()

    async def test_non_es_user_no_rfeg_call_needs_handicap_false(
        self, token_service, register_device_use_case
    ):
        """Usuario no-ES → no llama RFEG, needs_handicap=False."""
        uow = InMemoryUnitOfWork()
        user = User.create(
            first_name="Pierre",
            last_name="Dupont",
            email_str="fr@example.com",
            plain_password="V@l1dP@ss123!",
            country_code_str="FR",
        )
        async with uow:
            await uow.users.save(user)
            await uow.commit()

        handicap_svc = self._make_handicap_service(return_value=10.0)
        use_case = self._make_use_case(uow, token_service, register_device_use_case, handicap_svc)

        response = await use_case.execute(
            LoginRequestDTO(email="fr@example.com", password="V@l1dP@ss123!")
        )

        assert response is not None
        assert response.needs_handicap is False
        handicap_svc.search_handicap.assert_not_awaited()

    async def test_no_country_user_needs_handicap_false(
        self, token_service, register_device_use_case
    ):
        """Usuario sin country_code → needs_handicap=False."""
        uow = InMemoryUnitOfWork()
        user = User.create(
            first_name="Anonymous",
            last_name="User",
            email_str="anon@example.com",
            plain_password="V@l1dP@ss123!",
        )
        async with uow:
            await uow.users.save(user)
            await uow.commit()

        handicap_svc = self._make_handicap_service()
        use_case = self._make_use_case(uow, token_service, register_device_use_case, handicap_svc)

        response = await use_case.execute(
            LoginRequestDTO(email="anon@example.com", password="V@l1dP@ss123!")
        )

        assert response is not None
        assert response.needs_handicap is False
        handicap_svc.search_handicap.assert_not_awaited()

    async def test_existing_tests_unaffected_no_handicap_service(
        self, token_service, register_device_use_case
    ):
        """Sin handicap_service (tests existentes) → needs_handicap=False para usuarios no-ES."""
        uow = InMemoryUnitOfWork()
        user = User.create(
            first_name="John",
            last_name="Doe",
            email_str="john@example.com",
            plain_password="V@l1dP@ss123!",
        )
        async with uow:
            await uow.users.save(user)
            await uow.commit()

        use_case = self._make_use_case(uow, token_service, register_device_use_case, None)

        response = await use_case.execute(
            LoginRequestDTO(email="john@example.com", password="V@l1dP@ss123!")
        )

        assert response is not None
        assert response.needs_handicap is False
