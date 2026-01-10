"""
Tests para UserUnitOfWorkInterface - Verificación de contratos específicos

Estos tests verifican que la interfaz específica del Unit of Work para usuarios
define correctamente los contratos esperados.
"""

from abc import ABC
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from src.modules.user.domain.repositories.password_history_repository_interface import (
    PasswordHistoryRepositoryInterface,
)
from src.modules.user.domain.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)
from src.modules.user.domain.repositories.user_device_repository_interface import (
    UserDeviceRepositoryInterface,
)
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.shared.domain.repositories.unit_of_work_interface import UnitOfWorkInterface


class TestUserUnitOfWorkInterface:
    """Tests para verificar el contrato de UserUnitOfWorkInterface."""

    def test_user_unit_of_work_interface_is_abstract(self):
        """Verifica que UserUnitOfWorkInterface es una clase abstracta."""
        assert issubclass(UserUnitOfWorkInterface, ABC)

        # Debe lanzar TypeError al intentar instanciar directamente
        with pytest.raises(TypeError):
            UserUnitOfWorkInterface()

    def test_user_unit_of_work_inherits_from_base(self):
        """Verifica que UserUnitOfWorkInterface hereda de UnitOfWorkInterface."""
        assert issubclass(UserUnitOfWorkInterface, UnitOfWorkInterface)

    def test_user_unit_of_work_has_users_property(self):
        """Verifica que la interfaz define la propiedad users."""
        assert hasattr(UserUnitOfWorkInterface, "users")

    def test_users_property_signature(self):
        """Verifica la signatura de la propiedad users."""
        # Verificar que es una property abstracta
        users_property = UserUnitOfWorkInterface.users
        assert isinstance(users_property, property)

    def test_concrete_implementation_can_be_created(self):
        """Verifica que se puede crear una implementación concreta."""

        mock_user_repo = AsyncMock(spec=UserRepositoryInterface)
        mock_refresh_token_repo = AsyncMock(spec=RefreshTokenRepositoryInterface)
        mock_password_history_repo = AsyncMock(spec=PasswordHistoryRepositoryInterface)

        class MockUserUnitOfWork(UserUnitOfWorkInterface):
            def __init__(self):
                self._users = mock_user_repo
                self._refresh_tokens = mock_refresh_token_repo
                self._password_history = mock_password_history_repo
                self._active = False

            @property
            def users(self) -> UserRepositoryInterface:
                return self._users

            @property
            def refresh_tokens(self) -> RefreshTokenRepositoryInterface:
                return self._refresh_tokens

            @property
            def password_history(self) -> PasswordHistoryRepositoryInterface:
                return self._password_history

            @property
            def user_devices(self):
                return MagicMock()

            async def __aenter__(self):
                self._active = True
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                self._active = False

            async def commit(self) -> None:
                # Mock implementation - no operation needed for test
                pass

            async def rollback(self) -> None:
                # Mock implementation - no operation needed for test
                pass

            async def flush(self) -> None:
                # Mock implementation - no operation needed for test
                pass

            def is_active(self) -> bool:
                return self._active

        # Debe poder instanciarse sin problemas
        mock_uow = MockUserUnitOfWork()
        assert isinstance(mock_uow, UserUnitOfWorkInterface)
        assert isinstance(mock_uow, UnitOfWorkInterface)
        assert isinstance(mock_uow.users, UserRepositoryInterface)
        assert isinstance(mock_uow.refresh_tokens, RefreshTokenRepositoryInterface)
        assert isinstance(mock_uow.password_history, PasswordHistoryRepositoryInterface)

    def test_incomplete_implementation_fails(self):
        """Verifica que una implementación incompleta falla."""

        class IncompleteUserUnitOfWork(UserUnitOfWorkInterface):
            async def __aenter__(self):
                return self

            async def commit(self) -> None:
                pass

            # Falta la propiedad users y otros métodos...

        # Debe lanzar TypeError por métodos/propiedades abstractas faltantes
        with pytest.raises(TypeError):
            IncompleteUserUnitOfWork()


class TestUserUnitOfWorkContractCompliance:
    """Tests para verificar que cualquier implementación debe cumplir el contrato."""

    @pytest.fixture
    def mock_user_repository(self):
        """Crea un mock UserRepository."""
        return AsyncMock(spec=UserRepositoryInterface)

    @pytest.fixture
    def mock_user_unit_of_work(self, mock_user_repository):
        """Crea un mock UserUnitOfWork que cumple el contrato."""
        uow = AsyncMock(spec=UserUnitOfWorkInterface)
        uow.users = mock_user_repository
        uow.is_active.return_value = True
        return uow

    @pytest.mark.asyncio
    async def test_users_property_access(self, mock_user_unit_of_work):
        """Verifica que se puede acceder a la propiedad users."""
        user_repo = mock_user_unit_of_work.users
        assert isinstance(user_repo, UserRepositoryInterface)

    @pytest.mark.asyncio
    async def test_context_manager_with_user_repository(
        self, mock_user_unit_of_work, mock_user_repository
    ):
        """Verifica que el context manager funciona con el repositorio de usuarios."""
        mock_user_unit_of_work.__aenter__.return_value = mock_user_unit_of_work
        mock_user_unit_of_work.__aexit__.return_value = None

        async with mock_user_unit_of_work as uow:
            # Simular operaciones con el repositorio
            await uow.users.save(Mock())
            await uow.commit()

        mock_user_repository.save.assert_called_once()
        mock_user_unit_of_work.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_typical_use_case_pattern(self):
        """Verifica el patrón típico de uso en casos de uso."""

        class MockUserUnitOfWork(UserUnitOfWorkInterface):
            def __init__(self):
                self._user_repo = AsyncMock(spec=UserRepositoryInterface)
                self._refresh_token_repo = AsyncMock(spec=RefreshTokenRepositoryInterface)
                self._password_history_repo = AsyncMock(spec=PasswordHistoryRepositoryInterface)
                self._active = False
                self._committed = False

            @property
            def users(self) -> UserRepositoryInterface:
                return self._user_repo

            @property
            def refresh_tokens(self) -> RefreshTokenRepositoryInterface:
                return self._refresh_token_repo

            @property
            def password_history(self) -> PasswordHistoryRepositoryInterface:
                return self._password_history_repo

            @property
            def user_devices(self) -> UserDeviceRepositoryInterface:
                return AsyncMock(spec=UserDeviceRepositoryInterface)

            async def __aenter__(self):
                self._active = True
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None and self._active:
                    await self.commit()
                self._active = False

            async def commit(self) -> None:
                self._committed = True

            async def rollback(self) -> None:
                # Mock implementation - no operation needed for test
                pass

            async def flush(self) -> None:
                # Mock implementation - no operation needed for test
                pass

            def is_active(self) -> bool:
                return self._active

        # Simular caso de uso de registro de usuario
        uow = MockUserUnitOfWork()

        # Mock del email para evitar validaciones
        email = Mock()
        email.value = "test@example.com"

        # Configurar mocks
        uow.users.exists_by_email.return_value = False

        async with uow:
            # Verificar que email no existe
            exists = await uow.users.exists_by_email(email)
            assert exists is False

            # Crear y guardar usuario (mock)
            user = Mock()
            await uow.users.save(user)

        # Verificar que se llamaron los métodos correctos
        uow.users.exists_by_email.assert_called_once_with(email)
        uow.users.save.assert_called_once_with(user)
        assert uow._committed is True

    @pytest.mark.asyncio
    async def test_rollback_on_exception(self):
        """Verifica que se hace rollback cuando hay excepciones."""

        class TestUserUnitOfWork(UserUnitOfWorkInterface):
            def __init__(self):
                self._user_repo = AsyncMock(spec=UserRepositoryInterface)
                self._refresh_token_repo = AsyncMock(spec=RefreshTokenRepositoryInterface)
                self._password_history_repo = AsyncMock(spec=PasswordHistoryRepositoryInterface)
                self._active = False
                self._rolled_back = False

            @property
            def users(self) -> UserRepositoryInterface:
                return self._user_repo

            @property
            def refresh_tokens(self) -> RefreshTokenRepositoryInterface:
                return self._refresh_token_repo

            @property
            def password_history(self) -> PasswordHistoryRepositoryInterface:
                return self._password_history_repo

            @property
            def user_devices(self) -> UserDeviceRepositoryInterface:
                return AsyncMock(spec=UserDeviceRepositoryInterface)

            async def __aenter__(self):
                self._active = True
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if exc_type is not None:
                    await self.rollback()
                self._active = False

            async def commit(self) -> None:
                # Mock implementation - no operation needed for test
                pass

            async def rollback(self) -> None:
                self._rolled_back = True

            async def flush(self) -> None:
                # Mock implementation - no operation needed for test
                pass

            def is_active(self) -> bool:
                return self._active

        uow = TestUserUnitOfWork()

        # Simular excepción durante operación
        with pytest.raises(ValueError):
            async with uow:
                await uow.users.save(Mock())
                raise ValueError("Test error")

        # Verificar que se hizo rollback
        assert uow._rolled_back is True
        uow.users.save.assert_called_once()


class TestUserUnitOfWorkIntegration:
    """Tests de integración para verificar la cohesión entre componentes."""

    @pytest.mark.asyncio
    async def test_multiple_repository_operations(self):
        """Verifica múltiples operaciones de repositorio en una transacción."""

        class IntegrationUserUnitOfWork(UserUnitOfWorkInterface):
            def __init__(self):
                self._user_repo = AsyncMock(spec=UserRepositoryInterface)
                self._refresh_token_repo = AsyncMock(spec=RefreshTokenRepositoryInterface)
                self._password_history_repo = AsyncMock(spec=PasswordHistoryRepositoryInterface)
                self._operations = []
                self._committed = False

            @property
            def users(self) -> UserRepositoryInterface:
                return self._user_repo

            @property
            def refresh_tokens(self) -> RefreshTokenRepositoryInterface:
                return self._refresh_token_repo

            @property
            def password_history(self) -> PasswordHistoryRepositoryInterface:
                return self._password_history_repo

            @property
            def user_devices(self) -> UserDeviceRepositoryInterface:
                return AsyncMock(spec=UserDeviceRepositoryInterface)

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    await self.commit()

            async def commit(self) -> None:
                self._committed = True
                # Simular que todas las operaciones se confirman
                self._operations.append("COMMIT")

            async def rollback(self) -> None:
                self._operations.append("ROLLBACK")

            async def flush(self) -> None:
                self._operations.append("FLUSH")

            def is_active(self) -> bool:
                return True

        uow = IntegrationUserUnitOfWork()

        async with uow:
            # Múltiples operaciones en la misma transacción
            await uow.users.save(Mock())
            await uow.users.update(Mock())
            await uow.users.delete_by_id(Mock())
            await uow.flush()  # Flush intermedio
            await uow.users.save(Mock())

        # Verificar que todas las operaciones se ejecutaron
        assert uow.users.save.call_count == 2
        assert uow.users.update.call_count == 1
        assert uow.users.delete_by_id.call_count == 1
        assert uow._committed is True
        assert "FLUSH" in uow._operations
        assert "COMMIT" in uow._operations
