"""
Tests unitarios para el caso de uso ValidateResetTokenUseCase.

Este archivo contiene tests que verifican:
- Validación de tokens válidos y no expirados
- Manejo de tokens no existentes
- Manejo de tokens expirados (>24h)
- Mensajes apropiados para cada caso

Estructura:
- TestValidateResetTokenValid: Tests para tokens válidos
- TestValidateResetTokenInvalid: Tests para tokens inválidos/expirados
"""

from datetime import datetime, timedelta

import pytest

from src.modules.user.application.dto.user_dto import ValidateResetTokenRequestDTO
from src.modules.user.application.use_cases.validate_reset_token_use_case import (
    ValidateResetTokenUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

# Marcar todos los tests como asyncio
pytestmark = pytest.mark.asyncio


def _rebuild_user(user: User, **overrides) -> User:
    """
    Reconstruye un User con los mismos valores, sobrescribiendo los indicados.

    Tras la encapsulación de User (issue #109), sus atributos son de solo
    lectura vía @property. Los tests que necesitan simular un estado concreto
    (p.ej. un token ya expirado) reconstruyen la entidad en vez de mutar
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


class TestValidateResetTokenValid:
    """Tests para tokens válidos"""

    async def test_validate_reset_token_with_valid_token_returns_true(self, sample_user_data):
        """
        Test: Token válido retorna valid=True
        Given: Usuario con token recién generado
        When: Se valida el token
        Then: Retorna valid=True con mensaje de confirmación
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        use_case = ValidateResetTokenUseCase(uow)

        # Crear usuario con token válido
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        token = user.generate_password_reset_token()

        async with uow:
            await uow.users.save(user)

        request_dto = ValidateResetTokenRequestDTO(token=token)

        # Act
        response = await use_case.execute(request_dto)

        # Assert
        assert response.valid is True
        assert response.message == "Token válido. Puedes proceder con el reseteo de tu contraseña."

    async def test_validate_reset_token_with_valid_token_not_expired(self, sample_user_data):
        """
        Test: Token válido dentro del plazo de 24h retorna valid=True
        Given: Usuario con token generado hace 12 horas
        When: Se valida el token
        Then: Retorna valid=True (aún no expirado)
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        use_case = ValidateResetTokenUseCase(uow)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        token = user.generate_password_reset_token()

        # Simular que el token fue generado hace 12 horas (aún válido)
        user = _rebuild_user(user, reset_token_expires_at=datetime.now() + timedelta(hours=12))

        async with uow:
            await uow.users.save(user)

        request_dto = ValidateResetTokenRequestDTO(token=token)

        # Act
        response = await use_case.execute(request_dto)

        # Assert
        assert response.valid is True


class TestValidateResetTokenInvalid:
    """Tests para tokens inválidos o expirados"""

    async def test_validate_reset_token_with_nonexistent_token_returns_false(self):
        """
        Test: Token que no existe retorna valid=False
        Given: Token que no está en la BD
        When: Se valida el token
        Then: Retorna valid=False con mensaje genérico
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        use_case = ValidateResetTokenUseCase(uow)

        # Token válido de 43 caracteres pero que no existe en BD
        fake_token = "c" * 43

        request_dto = ValidateResetTokenRequestDTO(token=fake_token)

        # Act
        response = await use_case.execute(request_dto)

        # Assert
        assert response.valid is False
        assert response.message == "Token de reseteo inválido o expirado. Solicita un nuevo enlace."

    async def test_validate_reset_token_with_expired_token_returns_false(self, sample_user_data):
        """
        Test: Token expirado (>24h) retorna valid=False
        Given: Usuario con token expirado hace 2 horas
        When: Se valida el token
        Then: Retorna valid=False con mensaje de expiración
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        use_case = ValidateResetTokenUseCase(uow)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        token = user.generate_password_reset_token()

        # Simular expiración (hace 2 horas)
        user = _rebuild_user(user, reset_token_expires_at=datetime.now() - timedelta(hours=2))

        async with uow:
            await uow.users.save(user)

        request_dto = ValidateResetTokenRequestDTO(token=token)

        # Act
        response = await use_case.execute(request_dto)

        # Assert
        assert response.valid is False
        assert (
            response.message
            == "Token de reseteo expirado. Los tokens son válidos por 24 horas. Solicita un nuevo enlace."
        )

    async def test_validate_reset_token_at_exact_expiration_boundary(self, sample_user_data):
        """
        Test: Token exactamente en el momento de expiración retorna valid=False
        Given: Usuario con token que expira justo ahora
        When: Se valida el token
        Then: Retorna valid=False (expiración estricta)
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        use_case = ValidateResetTokenUseCase(uow)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        token = user.generate_password_reset_token()

        # Establecer expiración exactamente ahora (boundary)
        user = _rebuild_user(user, reset_token_expires_at=datetime.now())

        async with uow:
            await uow.users.save(user)

        request_dto = ValidateResetTokenRequestDTO(token=token)

        # Act
        response = await use_case.execute(request_dto)

        # Assert
        assert response.valid is False

    async def test_validate_reset_token_without_active_token_returns_false(self, sample_user_data):
        """
        Test: Usuario sin token activo retorna valid=False (edge case)
        Given: Usuario que tuvo token pero fue invalidado
        When: Se intenta validar con el token antiguo
        Then: Retorna valid=False con mensaje genérico
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        use_case = ValidateResetTokenUseCase(uow)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        token = user.generate_password_reset_token()

        # Invalidar el token manualmente (simulando que ya fue usado)
        user = _rebuild_user(user, password_reset_token=None, reset_token_expires_at=None)

        async with uow:
            await uow.users.save(user)

        request_dto = ValidateResetTokenRequestDTO(token=token)

        # Act
        response = await use_case.execute(request_dto)

        # Assert
        assert response.valid is False
        assert response.message == "Token de reseteo inválido o expirado. Solicita un nuevo enlace."

    async def test_validate_reset_token_with_wrong_token_for_existing_user(self, sample_user_data):
        """
        Test: Token incorrecto para usuario existente retorna valid=False
        Given: Usuario con token válido
        When: Se valida con un token diferente
        Then: Retorna valid=False (token no encontrado)
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        use_case = ValidateResetTokenUseCase(uow)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        # Generar token pero usar uno diferente para validar
        user.generate_password_reset_token()

        async with uow:
            await uow.users.save(user)

        # Token diferente al del usuario
        wrong_token = "d" * 43

        request_dto = ValidateResetTokenRequestDTO(token=wrong_token)

        # Act
        response = await use_case.execute(request_dto)

        # Assert
        assert response.valid is False
        assert response.message == "Token de reseteo inválido o expirado. Solicita un nuevo enlace."
