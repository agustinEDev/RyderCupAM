"""
Tests para UserOAuthAccountRepositoryInterface

Verificación del contrato del repositorio de OAuth accounts.
"""

from abc import ABC

import pytest

from src.modules.user.domain.repositories.user_oauth_account_repository_interface import (
    UserOAuthAccountRepositoryInterface,
)


class TestUserOAuthAccountRepositoryInterface:
    """Tests para verificar el contrato del repositorio."""

    def test_is_abstract(self):
        """Debe ser una clase abstracta."""
        assert issubclass(UserOAuthAccountRepositoryInterface, ABC)

        with pytest.raises(TypeError):
            UserOAuthAccountRepositoryInterface()

    def test_has_save_method(self):
        """Debe definir método save."""
        assert hasattr(UserOAuthAccountRepositoryInterface, "save")

    def test_has_find_by_provider_and_provider_user_id(self):
        """Debe definir método find_by_provider_and_provider_user_id."""
        assert hasattr(
            UserOAuthAccountRepositoryInterface,
            "find_by_provider_and_provider_user_id",
        )

    def test_has_find_by_user_id(self):
        """Debe definir método find_by_user_id."""
        assert hasattr(UserOAuthAccountRepositoryInterface, "find_by_user_id")

    def test_has_find_by_user_id_and_provider(self):
        """Debe definir método find_by_user_id_and_provider."""
        assert hasattr(
            UserOAuthAccountRepositoryInterface,
            "find_by_user_id_and_provider",
        )

    def test_has_delete_method(self):
        """Debe definir método delete."""
        assert hasattr(UserOAuthAccountRepositoryInterface, "delete")

    def test_defines_five_abstract_methods(self):
        """Debe tener exactamente 5 métodos abstractos."""
        abstract_methods = UserOAuthAccountRepositoryInterface.__abstractmethods__
        assert len(abstract_methods) == 5
