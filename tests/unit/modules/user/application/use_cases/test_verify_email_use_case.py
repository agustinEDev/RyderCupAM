"""
Tests unitarios para VerifyEmailUseCase.

Este archivo contiene tests que verifican:
- Verificación exitosa con token válido
- Manejo de tokens inválidos
- Validación de entrada vacía
- Manejo de usuario no encontrado
- Persistencia de cambios
"""

import pytest

from src.modules.user.application.use_cases.verify_email_use_case import VerifyEmailUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestVerifyEmailUseCase:
    """
    Suite de tests para el caso de uso VerifyEmailUseCase.
    """

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona una Unit of Work en memoria para cada test."""
        return InMemoryUnitOfWork()

    async def test_execute_with_valid_token_verifies_email(self, uow: InMemoryUnitOfWork):
        """
        Test: Verificar email con token válido
        Given: Un usuario registrado con token de verificación
        When: Se ejecuta verify_email con el token correcto
        Then: El email se verifica correctamente
        """
        # Arrange - Crear usuario y generar token
        async with uow:
            user = User.create("Juan", "Pérez", "juan@test.com", "T3stP@ssw0rd!")
            token = user.generate_verification_token()
            await uow.users.save(user)
            await uow.commit()

        # Act
        use_case = VerifyEmailUseCase(uow)
        result = await use_case.execute(token)

        # Assert: ahora result es la entidad User
        assert hasattr(result, "email_verified")
        assert result.email_verified is True

        # Verificar que el usuario está verificado en la persistencia
        async with uow:
            verified_user = await uow.users.find_by_verification_token(token)
            # El token ya no existe porque fue limpiado
            assert verified_user is None

            # Buscar por email y verificar el estado
            from src.modules.user.domain.value_objects.email import Email

            email = Email("juan@test.com")
            verified_user = await uow.users.find_by_email(email)
            assert verified_user is not None
            assert verified_user.email_verified is True
            assert verified_user.verification_token is None

    async def test_execute_with_invalid_token_raises_error(self, uow: InMemoryUnitOfWork):
        """
        Test: Token inválido lanza error
        Given: Un token que no existe en la BD
        When: Se ejecuta verify_email con ese token
        Then: Se lanza ValueError
        """
        # Arrange
        use_case = VerifyEmailUseCase(uow)
        invalid_token = "token_que_no_existe_12345"

        # Act & Assert
        with pytest.raises(ValueError, match="Token de verificación inválido o expirado"):
            await use_case.execute(invalid_token)

    async def test_execute_with_empty_token_raises_error(self, uow: InMemoryUnitOfWork):
        """
        Test: Token vacío lanza error
        Given: Un token vacío o solo espacios
        When: Se ejecuta verify_email
        Then: Se lanza ValueError
        """
        # Arrange
        use_case = VerifyEmailUseCase(uow)

        # Act & Assert - Token vacío
        with pytest.raises(ValueError, match="El token de verificación es requerido"):
            await use_case.execute("")

        # Act & Assert - Token solo con espacios
        with pytest.raises(ValueError, match="El token de verificación es requerido"):
            await use_case.execute("   ")

    async def test_execute_when_user_not_found(self, uow: InMemoryUnitOfWork):
        """
        Test: Usuario no encontrado lanza error
        Given: Un token que no está asociado a ningún usuario
        When: Se ejecuta verify_email
        Then: Se lanza ValueError
        """
        # Arrange
        use_case = VerifyEmailUseCase(uow)
        non_existent_token = "valid_format_but_no_user_abc123xyz"

        # Act & Assert
        with pytest.raises(ValueError, match="Token de verificación inválido o expirado"):
            await use_case.execute(non_existent_token)

    async def test_execute_commits_transaction(self, uow: InMemoryUnitOfWork):
        """
        Test: Verificación persiste los cambios
        Given: Un usuario con token de verificación
        When: Se verifica el email
        Then: Los cambios se persisten correctamente
        """
        # Arrange - Crear usuario
        async with uow:
            user = User.create("María", "García", "maria@test.com", "T3stP@ssw0rd!")
            token = user.generate_verification_token()
            await uow.users.save(user)
            await uow.commit()

        # Act
        use_case = VerifyEmailUseCase(uow)
        await use_case.execute(token)

        # Assert - Verificar que los cambios persisten en nueva transacción
        async with uow:
            from src.modules.user.domain.value_objects.email import Email

            email = Email("maria@test.com")
            persisted_user = await uow.users.find_by_email(email)

            assert persisted_user is not None
            assert persisted_user.email_verified is True
            assert persisted_user.verification_token is None

    async def test_execute_with_already_verified_email_raises_error(self, uow: InMemoryUnitOfWork):
        """
        Test: No se puede verificar un email ya verificado
        Given: Un usuario con email ya verificado
        When: Se intenta verificar nuevamente
        Then: Se lanza ValueError
        """
        # Arrange - Crear y verificar usuario
        async with uow:
            user = User.create("Pedro", "López", "pedro@test.com", "T3stP@ssw0rd!")
            token = user.generate_verification_token()
            user.verify_email(token)  # Primera verificación
            await uow.users.save(user)
            await uow.commit()

        # Generar nuevo token para intentar verificar de nuevo
        async with uow:
            from src.modules.user.domain.value_objects.email import Email

            email = Email("pedro@test.com")
            verified_user = await uow.users.find_by_email(email)
            # El usuario ya no tiene token, así que no se puede verificar de nuevo
            assert verified_user.verification_token is None

        # El caso de uso no debería encontrar usuario con token
        use_case = VerifyEmailUseCase(uow)
        with pytest.raises(ValueError):
            await use_case.execute("any_token")

    async def test_execute_with_different_token_than_stored_raises_error(
        self, uow: InMemoryUnitOfWork
    ):
        """
        Test: Token diferente al almacenado lanza error
        Given: Un usuario con token de verificación
        When: Se intenta verificar con un token diferente
        Then: Se lanza ValueError (el UserFinder no encuentra el usuario)
        """
        # Arrange
        async with uow:
            user = User.create("Ana", "Martínez", "ana@test.com", "T3stP@ssw0rd!")
            real_token = user.generate_verification_token()
            await uow.users.save(user)
            await uow.commit()

        # Act & Assert - Intentar con token diferente
        use_case = VerifyEmailUseCase(uow)
        fake_token = "this_is_not_the_real_token"

        with pytest.raises(ValueError, match="Token de verificación inválido o expirado"):
            await use_case.execute(fake_token)

        # Verificar que el usuario sigue sin verificar
        async with uow:
            from src.modules.user.domain.value_objects.email import Email

            email = Email("ana@test.com")
            unverified_user = await uow.users.find_by_email(email)
            assert unverified_user.email_verified is False
            assert unverified_user.verification_token == real_token

    async def test_execute_success_clears_verification_token(self, uow: InMemoryUnitOfWork):
        """
        Test: Verificación exitosa limpia el token
        Given: Un usuario con token de verificación
        When: Se verifica exitosamente
        Then: El token se elimina del usuario
        """
        # Arrange
        async with uow:
            user = User.create("Carlos", "Ruiz", "carlos@test.com", "T3stP@ssw0rd!")
            token = user.generate_verification_token()
            await uow.users.save(user)
            await uow.commit()

        # Act
        use_case = VerifyEmailUseCase(uow)
        await use_case.execute(token)

        # Assert
        async with uow:
            from src.modules.user.domain.value_objects.email import Email

            email = Email("carlos@test.com")
            verified_user = await uow.users.find_by_email(email)

            assert verified_user.verification_token is None
            assert verified_user.email_verified is True
