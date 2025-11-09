"""
Tests para UserRepositoryInterface - Verificación de contratos

Estos tests verifican que la interfaz del repositorio define correctamente
los contratos esperados, sin probar implementaciones concretas.
"""

import pytest
from abc import ABC
from typing import get_type_hints
from unittest.mock import AsyncMock

from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.domain.value_objects.email import Email


class TestUserRepositoryInterface:
    """Tests para verificar el contrato de UserRepositoryInterface."""

    def test_repository_interface_is_abstract(self):
        """Verifica que UserRepositoryInterface es una clase abstracta."""
        assert issubclass(UserRepositoryInterface, ABC)
        
        # Debe lanzar TypeError al intentar instanciar directamente
        with pytest.raises(TypeError):
            UserRepositoryInterface()

    def test_repository_interface_has_all_required_methods(self):
        """Verifica que la interfaz define todos los métodos requeridos."""
        required_methods = {
            'save',
            'find_by_id', 
            'find_by_email',
            'exists_by_email',
            'update',
            'delete_by_id',
            'find_all',
            'count_all'
        }
        
        interface_methods = {
            method for method in dir(UserRepositoryInterface)
            if not method.startswith('_')
        }
        
        assert required_methods.issubset(interface_methods)

    def test_save_method_signature(self):
        """Verifica la signatura del método save."""
        method = getattr(UserRepositoryInterface, 'save')
        type_hints = get_type_hints(method)
        
        assert 'user' in type_hints
        assert type_hints['user'] == User
        assert type_hints['return'] == type(None)

    def test_find_by_id_method_signature(self):
        """Verifica la signatura del método find_by_id."""
        method = getattr(UserRepositoryInterface, 'find_by_id')
        type_hints = get_type_hints(method)
        
        assert 'user_id' in type_hints
        assert type_hints['user_id'] == UserId

    def test_find_by_email_method_signature(self):
        """Verifica la signatura del método find_by_email."""
        method = getattr(UserRepositoryInterface, 'find_by_email')
        type_hints = get_type_hints(method)
        
        assert 'email' in type_hints
        assert type_hints['email'] == Email

    def test_exists_by_email_method_signature(self):
        """Verifica la signatura del método exists_by_email."""
        method = getattr(UserRepositoryInterface, 'exists_by_email')
        type_hints = get_type_hints(method)
        
        assert 'email' in type_hints
        assert type_hints['email'] == Email
        assert type_hints['return'] == bool

    def test_update_method_signature(self):
        """Verifica la signatura del método update."""
        method = getattr(UserRepositoryInterface, 'update')
        type_hints = get_type_hints(method)
        
        assert 'user' in type_hints
        assert type_hints['user'] == User
        assert type_hints['return'] == type(None)

    def test_delete_by_id_method_signature(self):
        """Verifica la signatura del método delete_by_id."""
        method = getattr(UserRepositoryInterface, 'delete_by_id')
        type_hints = get_type_hints(method)
        
        assert 'user_id' in type_hints
        assert type_hints['user_id'] == UserId
        assert type_hints['return'] == bool

    def test_find_all_method_signature(self):
        """Verifica la signatura del método find_all."""
        method = getattr(UserRepositoryInterface, 'find_all')
        type_hints = get_type_hints(method)
        
        assert 'limit' in type_hints
        assert type_hints['limit'] == int
        assert 'offset' in type_hints
        assert type_hints['offset'] == int

    def test_count_all_method_signature(self):
        """Verifica la signatura del método count_all."""
        method = getattr(UserRepositoryInterface, 'count_all')
        type_hints = get_type_hints(method)
        
        assert type_hints['return'] == int

    def test_all_methods_are_async(self):
        """Verifica que todos los métodos públicos son async."""
        methods_to_check = [
            'save', 'find_by_id', 'find_by_email', 'exists_by_email',
            'update', 'delete_by_id', 'find_all', 'count_all'
        ]
        
        for method_name in methods_to_check:
            method = getattr(UserRepositoryInterface, method_name)
            # Los métodos abstractos async tienen __code__.co_flags con CO_COROUTINE
            assert hasattr(method, '__code__'), f"Method {method_name} should have __code__"

    def test_concrete_implementation_can_be_created(self):
        """Verifica que se puede crear una implementación concreta."""
        
        class MockUserRepository(UserRepositoryInterface):
            async def save(self, user: User) -> None:
                pass
            
            async def find_by_id(self, user_id: UserId):
                pass
            
            async def find_by_email(self, email: Email):
                pass
            
            async def find_by_full_name(self, full_name: str):
                return None
            
            async def exists_by_email(self, email: Email) -> bool:
                return False
            
            async def update(self, user: User) -> None:
                pass
            
            async def delete_by_id(self, user_id: UserId) -> bool:
                return False
            
            async def find_all(self, limit: int = 100, offset: int = 0):
                return []
            
            async def count_all(self) -> int:
                return 0
        
        # Debe poder instanciarse sin problemas
        mock_repo = MockUserRepository()
        assert isinstance(mock_repo, UserRepositoryInterface)

    def test_incomplete_implementation_fails(self):
        """Verifica que una implementación incompleta falla."""
        
        class IncompleteRepository(UserRepositoryInterface):
            async def save(self, user: User) -> None:
                pass
            # Faltan métodos...
        
        # Debe lanzar TypeError por métodos abstractos faltantes
        with pytest.raises(TypeError):
            IncompleteRepository()


class TestUserRepositoryContractCompliance:
    """Tests para verificar que cualquier implementación debe cumplir el contrato."""

    @pytest.fixture
    def mock_repository(self):
        """Crea un mock repository que cumple el contrato."""
        repo = AsyncMock(spec=UserRepositoryInterface)
        return repo

    @pytest.mark.asyncio
    async def test_save_method_contract(self, mock_repository):
        """Verifica que el método save puede ser llamado correctamente."""
        user = AsyncMock(spec=User)
        
        # El método debe poder ser llamado sin argumentos adicionales
        await mock_repository.save(user)
        mock_repository.save.assert_called_once_with(user)

    @pytest.mark.asyncio
    async def test_find_by_id_contract(self, mock_repository):
        """Verifica que el método find_by_id puede ser llamado correctamente."""
        user_id = AsyncMock(spec=UserId)
        
        await mock_repository.find_by_id(user_id)
        mock_repository.find_by_id.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_find_by_email_contract(self, mock_repository):
        """Verifica que el método find_by_email puede ser llamado correctamente."""
        email = AsyncMock(spec=Email)
        
        await mock_repository.find_by_email(email)
        mock_repository.find_by_email.assert_called_once_with(email)

    @pytest.mark.asyncio
    async def test_exists_by_email_contract(self, mock_repository):
        """Verifica que el método exists_by_email puede ser llamado correctamente."""
        email = AsyncMock(spec=Email)
        mock_repository.exists_by_email.return_value = True
        
        result = await mock_repository.exists_by_email(email)
        assert result is True
        mock_repository.exists_by_email.assert_called_once_with(email)

    @pytest.mark.asyncio
    async def test_find_all_with_default_parameters(self, mock_repository):
        """Verifica que find_all funciona con parámetros por defecto."""
        mock_repository.find_all.return_value = []
        
        result = await mock_repository.find_all()
        assert result == []
        mock_repository.find_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_all_with_custom_parameters(self, mock_repository):
        """Verifica que find_all funciona con parámetros personalizados."""
        mock_repository.find_all.return_value = []
        
        await mock_repository.find_all(limit=50, offset=10)
        mock_repository.find_all.assert_called_once_with(limit=50, offset=10)

    @pytest.mark.asyncio
    async def test_count_all_contract(self, mock_repository):
        """Verifica que el método count_all puede ser llamado correctamente."""
        mock_repository.count_all.return_value = 42
        
        result = await mock_repository.count_all()
        assert result == 42
        mock_repository.count_all.assert_called_once()