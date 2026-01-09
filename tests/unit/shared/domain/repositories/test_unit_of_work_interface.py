"""
Tests para UnitOfWorkInterface - Verificación de contratos base

Estos tests verifican que la interfaz base del Unit of Work define correctamente
los contratos esperados para la gestión de transacciones.
"""

from abc import ABC
from typing import get_type_hints
from unittest.mock import AsyncMock

import pytest

from src.shared.domain.repositories.unit_of_work_interface import UnitOfWorkInterface


class TestUnitOfWorkInterface:
    """Tests para verificar el contrato base de UnitOfWorkInterface."""

    def test_unit_of_work_interface_is_abstract(self):
        """Verifica que UnitOfWorkInterface es una clase abstracta."""
        assert issubclass(UnitOfWorkInterface, ABC)

        # Debe lanzar TypeError al intentar instanciar directamente
        with pytest.raises(TypeError):
            UnitOfWorkInterface()

    def test_unit_of_work_interface_has_all_required_methods(self):
        """Verifica que la interfaz define todos los métodos requeridos."""
        required_methods = {"__aenter__", "__aexit__", "commit", "rollback", "flush", "is_active"}

        interface_methods = {
            method
            for method in dir(UnitOfWorkInterface)
            if not method.startswith("_") or method.startswith("__a")
        }

        assert required_methods.issubset(interface_methods)

    def test_aenter_method_signature(self):
        """Verifica la signatura del método __aenter__."""
        # __aenter__ debe retornar el propio UnitOfWork
        # En este caso, no podemos verificar el return type específico
        # porque es abstracto, pero podemos verificar que existe
        assert hasattr(UnitOfWorkInterface, "__aenter__")

    def test_aexit_method_signature(self):
        """Verifica la signatura del método __aexit__."""
        # __aexit__ debe aceptar exc_type, exc_val, exc_tb
        assert hasattr(UnitOfWorkInterface, "__aexit__")

    def test_commit_method_signature(self):
        """Verifica la signatura del método commit."""
        method = UnitOfWorkInterface.commit
        type_hints = get_type_hints(method)

        assert type_hints["return"] == type(None)

    def test_rollback_method_signature(self):
        """Verifica la signatura del método rollback."""
        method = UnitOfWorkInterface.rollback
        type_hints = get_type_hints(method)

        assert type_hints["return"] == type(None)

    def test_flush_method_signature(self):
        """Verifica la signatura del método flush."""
        method = UnitOfWorkInterface.flush
        type_hints = get_type_hints(method)

        assert type_hints["return"] == type(None)

    def test_is_active_method_signature(self):
        """Verifica la signatura del método is_active."""
        method = UnitOfWorkInterface.is_active
        type_hints = get_type_hints(method)

        assert type_hints["return"] == bool

    def test_interface_is_async_context_manager(self):
        """Verifica que la interfaz implementa AsyncContextManager."""
        from typing import AsyncContextManager

        # UnitOfWorkInterface debe ser un AsyncContextManager
        assert issubclass(UnitOfWorkInterface, AsyncContextManager)

    def test_concrete_implementation_can_be_created(self):
        """Verifica que se puede crear una implementación concreta."""

        class MockUnitOfWork(UnitOfWorkInterface):
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                # Mock implementation - context manager cleanup
                pass

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
                return True

        # Debe poder instanciarse sin problemas
        mock_uow = MockUnitOfWork()
        assert isinstance(mock_uow, UnitOfWorkInterface)
        assert mock_uow.is_active() is True

    def test_incomplete_implementation_fails(self):
        """Verifica que una implementación incompleta falla."""

        class IncompleteUnitOfWork(UnitOfWorkInterface):
            async def __aenter__(self):
                return self

            async def commit(self) -> None:
                pass

            # Faltan métodos...

        # Debe lanzar TypeError por métodos abstractos faltantes
        with pytest.raises(TypeError):
            IncompleteUnitOfWork()


class TestUnitOfWorkContractCompliance:
    """Tests para verificar que cualquier implementación debe cumplir el contrato."""

    @pytest.fixture
    def mock_unit_of_work(self):
        """Crea un mock Unit of Work que cumple el contrato."""
        uow = AsyncMock(spec=UnitOfWorkInterface)
        uow.is_active.return_value = True
        return uow

    @pytest.mark.asyncio
    async def test_context_manager_protocol(self, mock_unit_of_work):
        """Verifica que el protocolo de context manager funciona."""
        mock_unit_of_work.__aenter__.return_value = mock_unit_of_work
        mock_unit_of_work.__aexit__.return_value = None

        async with mock_unit_of_work as uow:
            assert uow is mock_unit_of_work

        mock_unit_of_work.__aenter__.assert_called_once()
        mock_unit_of_work.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_commit_method_contract(self, mock_unit_of_work):
        """Verifica que el método commit puede ser llamado correctamente."""
        await mock_unit_of_work.commit()
        mock_unit_of_work.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_method_contract(self, mock_unit_of_work):
        """Verifica que el método rollback puede ser llamado correctamente."""
        await mock_unit_of_work.rollback()
        mock_unit_of_work.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_method_contract(self, mock_unit_of_work):
        """Verifica que el método flush puede ser llamado correctamente."""
        await mock_unit_of_work.flush()
        mock_unit_of_work.flush.assert_called_once()

    def test_is_active_method_contract(self, mock_unit_of_work):
        """Verifica que el método is_active puede ser llamado correctamente."""
        result = mock_unit_of_work.is_active()
        assert result is True
        mock_unit_of_work.is_active.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_handling_in_context(self):
        """Verifica que las excepciones se manejan correctamente en el contexto."""

        class TestUnitOfWork(UnitOfWorkInterface):
            def __init__(self):
                self._committed = False
                self._rolled_back = False

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if exc_type is not None:
                    await self.rollback()
                else:
                    await self.commit()

            async def commit(self) -> None:
                self._committed = True

            async def rollback(self) -> None:
                self._rolled_back = True

            async def flush(self) -> None:
                # Mock implementation - no operation needed for test
                pass

            def is_active(self) -> bool:
                return True

        # Test sin excepción - debe hacer commit
        uow = TestUnitOfWork()
        async with uow:
            # Empty context for testing commit on success
            pass

        assert uow._committed is True
        assert uow._rolled_back is False

        # Test con excepción - debe hacer rollback
        uow2 = TestUnitOfWork()
        with pytest.raises(ValueError):
            async with uow2:
                raise ValueError("Test exception")

        assert uow2._committed is False
        assert uow2._rolled_back is True


class TestUnitOfWorkUsagePatterns:
    """Tests para verificar patrones de uso típicos del Unit of Work."""

    @pytest.mark.asyncio
    async def test_typical_usage_pattern(self):
        """Verifica el patrón de uso típico del Unit of Work."""

        class MockRepository:
            def __init__(self):
                self.saved_items = []

            def save(self, item):
                self.saved_items.append(item)

        class UseCaseUnitOfWork(UnitOfWorkInterface):
            def __init__(self):
                self.repository = MockRepository()
                self._active = False
                self._committed = False

            async def __aenter__(self):
                self._active = True
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
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

        # Simular caso de uso típico
        uow = UseCaseUnitOfWork()

        async with uow:
            assert uow.is_active() is True
            uow.repository.save("test_item")

        assert uow.is_active() is False
        assert uow._committed is True
        assert len(uow.repository.saved_items) == 1
        assert uow.repository.saved_items[0] == "test_item"
