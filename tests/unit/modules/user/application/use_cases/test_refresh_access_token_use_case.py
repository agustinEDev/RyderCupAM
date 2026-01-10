"""
Tests para RefreshAccessTokenUseCase.

Tests unitarios para el caso de uso de renovación de access tokens usando refresh tokens.
Session Timeout feature (v1.8.0 - OWASP A01/A02/A07).

Arquitectura:
- Capa: Unit Tests (Application)
- Módulo: User
- Feature: Session Timeout with Refresh Tokens
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from src.modules.user.application.dto.user_dto import (
    RefreshAccessTokenRequestDTO,
    RefreshAccessTokenResponseDTO,
)
from src.modules.user.application.use_cases.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.refresh_token_id import RefreshTokenId
from src.modules.user.domain.value_objects.token_hash import TokenHash
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


@pytest.mark.asyncio
class TestRefreshAccessTokenUseCase:
    """Tests para el caso de uso RefreshAccessTokenUseCase."""

    @pytest.fixture
    def uow(self):
        """Fixture que proporciona un Unit of Work en memoria."""
        return InMemoryUnitOfWork()

    @pytest.fixture
    def token_service(self):
        """Fixture que proporciona un mock del servicio de tokens."""
        service = Mock()
        # Configurar métodos por defecto
        # verify_refresh_token es SYNC (no async)
        service.verify_refresh_token.return_value = None
        # create_access_token es SYNC (no async)
        service.create_access_token.return_value = "new_access_token_jwt"
        return service

    @pytest.fixture
    def register_device_use_case(self):
        """Fixture que proporciona un mock del RegisterDeviceUseCase (v1.13.0)."""
        mock = AsyncMock()
        mock.execute.return_value = AsyncMock()  # RegisterDeviceResponseDTO mock
        return mock

    @pytest.fixture
    def use_case(self, uow, token_service, register_device_use_case):
        """Fixture que proporciona el use case con dependencias mockeadas."""
        return RefreshAccessTokenUseCase(uow, token_service, register_device_use_case)

    @pytest.fixture
    def sample_user(self):
        """Fixture que crea un usuario de prueba."""
        return User.create(
            first_name="John",
            last_name="Doe",
            email_str="user@example.com",
            plain_password="SecureP@ssw0rd123!",
        )

    @pytest.fixture
    def valid_refresh_token_jwt(self):
        """Fixture que proporciona un JWT de refresh token válido."""
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.valid_refresh_token"

    @pytest.fixture
    def refresh_token_entity(self, sample_user, valid_refresh_token_jwt):
        """Fixture que crea una entidad RefreshToken válida."""
        return RefreshToken.create(
            user_id=sample_user.id, token=valid_refresh_token_jwt, expires_in_days=7
        )

    async def test_execute_with_valid_refresh_token_returns_new_access_token(
        self,
        use_case,
        uow,
        token_service,
        sample_user,
        valid_refresh_token_jwt,
        refresh_token_entity,
    ):
        """
        Test: execute() con refresh token válido retorna nuevo access token.

        Given:
            - Un refresh token JWT válido
            - Un refresh token entity en BD no revocado y no expirado
            - Un usuario existente

        When: Se ejecuta el use case

        Then:
            - Retorna RefreshAccessTokenResponseDTO con nuevo access token
            - access_token es el generado por token_service
            - token_type es "bearer"
            - user contiene datos del usuario
        """
        # Given
        request = RefreshAccessTokenRequestDTO()

        # Configurar token_service para que verifique exitosamente el refresh token
        token_service.verify_refresh_token.return_value = {
            "sub": str(sample_user.id.value),
            "type": "refresh",
        }

        # Guardar usuario y refresh token en UoW
        await uow.users.save(sample_user)
        await uow.refresh_tokens.save(refresh_token_entity)

        # When
        result = await use_case.execute(request, valid_refresh_token_jwt)

        # Then
        assert result is not None
        assert isinstance(result, RefreshAccessTokenResponseDTO)
        assert result.access_token == "new_access_token_jwt"
        assert result.token_type == "bearer"
        assert result.user.email == sample_user.email.value
        assert result.user.first_name == sample_user.first_name
        assert result.message == "Access token renovado exitosamente"

        # Verificar que se llamaron los servicios correctos
        token_service.verify_refresh_token.assert_called_once_with(valid_refresh_token_jwt)
        token_service.create_access_token.assert_called_once()

    async def test_execute_with_invalid_jwt_returns_none(
        self,
        use_case,
        token_service,
    ):
        """
        Test: execute() con JWT inválido retorna None.

        Given: Un refresh token JWT con firma inválida o expirado
        When: Se ejecuta el use case
        Then: Retorna None (token_service.verify_refresh_token retorna None)
        """
        # Given
        request = RefreshAccessTokenRequestDTO()
        invalid_token = "invalid.jwt.token"

        # token_service verifica y retorna None (inválido)
        token_service.verify_refresh_token.return_value = None

        # When
        result = await use_case.execute(request, invalid_token)

        # Then
        assert result is None
        token_service.verify_refresh_token.assert_called_once_with(invalid_token)

    async def test_execute_with_missing_sub_in_payload_returns_none(
        self,
        use_case,
        token_service,
    ):
        """
        Test: execute() con payload sin 'sub' retorna None.

        Given: Un refresh token JWT válido pero sin claim 'sub'
        When: Se ejecuta el use case
        Then: Retorna None
        """
        # Given
        request = RefreshAccessTokenRequestDTO()
        token = "eyJhbGciOiJIUzI1NiJ9.no_sub"

        # Payload sin 'sub'
        token_service.verify_refresh_token.return_value = {"type": "refresh"}

        # When
        result = await use_case.execute(request, token)

        # Then
        assert result is None

    async def test_execute_with_invalid_user_id_returns_none(
        self,
        use_case,
        token_service,
    ):
        """
        Test: execute() con user_id inválido (no UUID) retorna None.

        Given: Un refresh token JWT con 'sub' que no es UUID válido
        When: Se ejecuta el use case
        Then: Retorna None (ValueError al crear UserId)
        """
        # Given
        request = RefreshAccessTokenRequestDTO()
        token = "eyJhbGciOiJIUzI1NiJ9.invalid_user_id"

        token_service.verify_refresh_token.return_value = {
            "sub": "not-a-valid-uuid",
            "type": "refresh",
        }

        # When
        result = await use_case.execute(request, token)

        # Then
        assert result is None

    async def test_execute_with_token_not_in_database_returns_none(
        self,
        use_case,
        uow,
        token_service,
        sample_user,
    ):
        """
        Test: execute() cuando refresh token no existe en BD retorna None.

        Given:
            - Un refresh token JWT válido (firma OK)
            - Pero el token NO está guardado en la base de datos

        When: Se ejecuta el use case
        Then: Retorna None
        """
        # Given
        request = RefreshAccessTokenRequestDTO()
        token = "eyJhbGciOiJIUzI1NiJ9.not_in_db"

        token_service.verify_refresh_token.return_value = {
            "sub": str(sample_user.id.value),
            "type": "refresh",
        }

        # Usuario existe, pero refresh token NO
        await uow.users.save(sample_user)

        # When
        result = await use_case.execute(request, token)

        # Then
        assert result is None

    async def test_execute_with_revoked_token_returns_none(
        self,
        use_case,
        uow,
        token_service,
        sample_user,
        valid_refresh_token_jwt,
        refresh_token_entity,
    ):
        """
        Test: execute() con refresh token revocado retorna None.

        Given:
            - Un refresh token JWT válido
            - Token existe en BD pero está revocado

        When: Se ejecuta el use case
        Then: Retorna None
        """
        # Given
        request = RefreshAccessTokenRequestDTO()

        token_service.verify_refresh_token.return_value = {
            "sub": str(sample_user.id.value),
            "type": "refresh",
        }

        # Guardar usuario y refresh token revocado
        await uow.users.save(sample_user)
        refresh_token_entity.revoke()  # Revocar antes de guardar
        await uow.refresh_tokens.save(refresh_token_entity)

        # When
        result = await use_case.execute(request, valid_refresh_token_jwt)

        # Then
        assert result is None

    async def test_execute_with_expired_token_returns_none(
        self,
        use_case,
        uow,
        token_service,
        sample_user,
    ):
        """
        Test: execute() con refresh token expirado retorna None.

        Given:
            - Un refresh token JWT válido (firma OK)
            - Token existe en BD pero está expirado

        When: Se ejecuta el use case
        Then: Retorna None
        """
        # Given
        request = RefreshAccessTokenRequestDTO()
        token = "eyJhbGciOiJIUzI1NiJ9.expired"

        token_service.verify_refresh_token.return_value = {
            "sub": str(sample_user.id.value),
            "type": "refresh",
        }

        # Crear refresh token entity expirado
        token_hash = TokenHash.from_token(token)
        expires_at = datetime.now() - timedelta(days=1)  # Expirado hace 1 día

        expired_token = RefreshToken(
            id=RefreshTokenId.generate(),
            user_id=sample_user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        await uow.users.save(sample_user)
        await uow.refresh_tokens.save(expired_token)

        # When
        result = await use_case.execute(request, token)

        # Then
        assert result is None

    async def test_execute_when_user_not_exists_returns_none(
        self,
        use_case,
        uow,
        token_service,
        sample_user,
        valid_refresh_token_jwt,
        refresh_token_entity,
    ):
        """
        Test: execute() cuando el usuario no existe retorna None.

        Given:
            - Un refresh token JWT válido
            - Token existe en BD y no está revocado
            - PERO el usuario fue eliminado

        When: Se ejecuta el use case
        Then: Retorna None
        """
        # Given
        request = RefreshAccessTokenRequestDTO()

        token_service.verify_refresh_token.return_value = {
            "sub": str(sample_user.id.value),
            "type": "refresh",
        }

        # Guardar solo refresh token, NO el usuario
        await uow.refresh_tokens.save(refresh_token_entity)

        # When
        result = await use_case.execute(request, valid_refresh_token_jwt)

        # Then
        assert result is None

    async def test_execute_creates_new_access_token_with_user_id(
        self,
        use_case,
        uow,
        token_service,
        sample_user,
        valid_refresh_token_jwt,
        refresh_token_entity,
    ):
        """
        Test: execute() crea nuevo access token con user_id correcto.

        Given: Refresh token válido
        When: Se ejecuta el use case
        Then: token_service.create_access_token es llamado con {"sub": user_id}
        """
        # Given
        request = RefreshAccessTokenRequestDTO()

        token_service.verify_refresh_token.return_value = {
            "sub": str(sample_user.id.value),
            "type": "refresh",
        }

        await uow.users.save(sample_user)
        await uow.refresh_tokens.save(refresh_token_entity)

        # When
        result = await use_case.execute(request, valid_refresh_token_jwt)

        # Then
        assert result is not None
        # Verificar que create_access_token fue llamado con el user_id correcto
        call_args = token_service.create_access_token.call_args
        assert call_args is not None
        assert call_args[1]["data"]["sub"] == str(sample_user.id.value)

    async def test_execute_does_not_modify_refresh_token(
        self,
        use_case,
        uow,
        token_service,
        sample_user,
        valid_refresh_token_jwt,
        refresh_token_entity,
    ):
        """
        Test: execute() NO modifica el refresh token (no lo renueva automáticamente).

        Given: Refresh token válido
        When: Se ejecuta el use case exitosamente
        Then:
            - El refresh token en BD no cambia
            - No se crea un nuevo refresh token
        """
        # Given
        request = RefreshAccessTokenRequestDTO()

        token_service.verify_refresh_token.return_value = {
            "sub": str(sample_user.id.value),
            "type": "refresh",
        }

        await uow.users.save(sample_user)
        await uow.refresh_tokens.save(refresh_token_entity)

        original_token_hash = refresh_token_entity.token_hash.value
        original_expires_at = refresh_token_entity.expires_at

        # When
        result = await use_case.execute(request, valid_refresh_token_jwt)

        # Then
        assert result is not None

        # Verificar que el refresh token NO cambió
        saved_token = await uow.refresh_tokens.find_by_token_hash(valid_refresh_token_jwt)
        assert saved_token is not None
        assert saved_token.token_hash.value == original_token_hash
        assert saved_token.expires_at == original_expires_at
        assert saved_token.revoked is False
