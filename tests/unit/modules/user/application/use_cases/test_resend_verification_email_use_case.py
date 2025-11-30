"""
Tests unitarios para ResendVerificationEmailUseCase.

Este archivo contiene tests que verifican:
- Reenvío exitoso con email válido
- Manejo de email no encontrado
- Validación de email vacío
- Prevención de reenvío a emails ya verificados
- Generación de nuevo token
- Persistencia de cambios
"""

from unittest.mock import MagicMock

import pytest

from src.modules.user.application.use_cases.resend_verification_email_use_case import (
    ResendVerificationEmailUseCase,
    ResendVerificationError,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestResendVerificationEmailUseCase:
    """
    Suite de tests para el caso de uso ResendVerificationEmailUseCase.
    """

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona una Unit of Work en memoria para cada test."""
        return InMemoryUnitOfWork()

    @pytest.fixture
    def email_service_mock(self) -> MagicMock:
        """Fixture que proporciona un mock del servicio de email."""
        mock = MagicMock()
        mock.send_verification_email.return_value = True
        return mock

    async def test_execute_with_valid_email_sends_verification_email(
        self,
        uow: InMemoryUnitOfWork,
        email_service_mock: MagicMock
    ):
        """
        Test: Reenviar email con dirección válida
        Given: Un usuario registrado pero no verificado
        When: Se ejecuta resend_verification_email con su email
        Then: Se genera nuevo token y se envía el email
        """
        # Crear usuario sin verificar
        async with uow:
            user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
            old_token = user.generate_verification_token()
            await uow.users.save(user)
            await uow.commit()

        # Act
        use_case = ResendVerificationEmailUseCase(uow, email_service_mock)
        result = await use_case.execute("juan@test.com")

        # Assert
        assert result is True
        email_service_mock.send_verification_email.assert_called_once()

        # Verificar que se generó un nuevo token
        async with uow:
            from src.modules.user.domain.value_objects.email import Email
            email = Email("juan@test.com")
            updated_user = await uow.users.find_by_email(email)

            assert updated_user is not None
            assert updated_user.verification_token is not None
            assert updated_user.verification_token != old_token  # Debe ser diferente

    async def test_execute_with_nonexistent_email_raises_error(self, uow: InMemoryUnitOfWork):
        """
        Test: Email no encontrado lanza error genérico
        Given: Un email que no existe en la BD
        When: Se ejecuta resend_verification_email
        Then: Se lanza ValueError con mensaje genérico (seguridad: prevención de user enumeration)
        """
        # Arrange
        use_case = ResendVerificationEmailUseCase(uow)

        # Act & Assert
        with pytest.raises(ResendVerificationError, match="Si el email existe y no está verificado, se enviará un email de verificación"):
            await use_case.execute("noexiste@test.com")

    async def test_execute_with_empty_email_raises_error(self, uow: InMemoryUnitOfWork):
        """
        Test: Email vacío lanza error
        Given: Un email vacío o solo espacios
        When: Se ejecuta resend_verification_email
        Then: Se lanza ValueError
        """
        # Arrange
        use_case = ResendVerificationEmailUseCase(uow)

        # Act & Assert - Email vacío
        with pytest.raises(ResendVerificationError, match="El email es requerido"):
            await use_case.execute("")

        # Act & Assert - Email solo con espacios
        with pytest.raises(ResendVerificationError, match="El email es requerido"):
            await use_case.execute("   ")

    async def test_execute_with_verified_email_raises_error(self, uow: InMemoryUnitOfWork):
        """
        Test: Email ya verificado lanza error genérico
        Given: Un usuario con email ya verificado
        When: Se intenta reenviar verificación
        Then: Se lanza ValueError con mensaje genérico (seguridad: prevención de user enumeration)
        """
        # Arrange - Crear usuario y verificarlo
        async with uow:
            user = User.create("María", "García", "maria@test.com", "Password123!")
            token = user.generate_verification_token()
            user.verify_email(token)  # Verificar el email
            await uow.users.save(user)
            await uow.commit()

        # Act & Assert
        use_case = ResendVerificationEmailUseCase(uow)
        with pytest.raises(ResendVerificationError, match="Si el email existe y no está verificado, se enviará un email de verificación"):
            await use_case.execute("maria@test.com")

    async def test_execute_generates_new_token(
        self,
        uow: InMemoryUnitOfWork,
        email_service_mock: MagicMock
    ):
        """
        Test: Se genera un nuevo token de verificación
        Given: Un usuario con token existente
        When: Se reenvía la verificación
        Then: Se genera un nuevo token diferente al anterior
        """
        async with uow:
            user = User.create("Pedro", "López", "pedro@test.com", "Password123!")
            old_token = user.generate_verification_token()
            await uow.users.save(user)
            await uow.commit()

        # Act
        use_case = ResendVerificationEmailUseCase(uow, email_service_mock)
        await use_case.execute("pedro@test.com")

        # Assert - Verificar que el token cambió
        async with uow:
            from src.modules.user.domain.value_objects.email import Email
            email = Email("pedro@test.com")
            updated_user = await uow.users.find_by_email(email)

            assert updated_user.verification_token is not None
            assert updated_user.verification_token != old_token

    async def test_execute_commits_transaction(
        self,
        uow: InMemoryUnitOfWork,
        email_service_mock: MagicMock
    ):
        """
        Test: Reenvío persiste los cambios
        Given: Un usuario sin verificar
        When: Se reenvía la verificación
        Then: Los cambios se persisten correctamente
        """
        async with uow:
            user = User.create("Ana", "Martínez", "ana@test.com", "Password123!")
            user.generate_verification_token()
            await uow.users.save(user)
            await uow.commit()

        # Act
        use_case = ResendVerificationEmailUseCase(uow, email_service_mock)
        await use_case.execute("ana@test.com")

        # Assert - Verificar que los cambios persisten en nueva transacción
        async with uow:
            from src.modules.user.domain.value_objects.email import Email
            email = Email("ana@test.com")
            persisted_user = await uow.users.find_by_email(email)

            assert persisted_user is not None
            assert persisted_user.verification_token is not None
            assert persisted_user.email_verified is False

    async def test_execute_when_email_service_fails_raises_error(
        self,
        uow: InMemoryUnitOfWork
    ):
        """
        Test: Error al enviar email lanza excepción y NO guarda token
        Given: Un usuario válido pero el servicio de email falla
        When: Se intenta reenviar la verificación
        Then: Se lanza ValueError y no se guarda ningún token en BD
        """
        # Arrange - Mock del servicio de email para que falle
        email_service_mock_fail = MagicMock()
        email_service_mock_fail.send_verification_email.return_value = False

        async with uow:
            user = User.create("Carlos", "Ruiz", "carlos@test.com", "Password123!")
            original_token = user.generate_verification_token()
            await uow.users.save(user)
            await uow.commit()

        # Act & Assert
        use_case = ResendVerificationEmailUseCase(uow, email_service_mock_fail)
        with pytest.raises(ResendVerificationError, match="Error al enviar el email de verificación"):
            await use_case.execute("carlos@test.com")

        # Verificar que NO se guardó ningún token nuevo en la BD
        async with uow:
            from src.modules.user.domain.value_objects.email import Email
            email = Email("carlos@test.com")
            user_after = await uow.users.find_by_email(email)
            assert user_after is not None
            assert user_after.verification_token == original_token  # Token no cambió

    async def test_execute_calls_email_service_with_correct_params(
        self,
        uow: InMemoryUnitOfWork,
        email_service_mock: MagicMock
    ):
        """
        Test: Servicio de email se llama con parámetros correctos
        Given: Un usuario válido
        When: Se reenvía la verificación
        Then: El servicio de email se llama con los parámetros correctos
        """
        async with uow:
            user = User.create("Luis", "Fernández", "luis@test.com", "Password123!")
            user.generate_verification_token()
            await uow.users.save(user)
            await uow.commit()

        # Act
        use_case = ResendVerificationEmailUseCase(uow, email_service_mock)
        await use_case.execute("luis@test.com")

        # Assert
        call_args = email_service_mock.send_verification_email.call_args
        assert call_args is not None
        assert call_args.kwargs['to_email'] == "luis@test.com"
        assert call_args.kwargs['user_name'] == "Luis Fernández"
        assert isinstance(call_args.kwargs['verification_token'], str)
        assert len(call_args.kwargs['verification_token']) > 0
