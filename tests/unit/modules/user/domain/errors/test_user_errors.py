"""
Tests para User Domain Errors - Verificación de excepciones

Tests que verifican el comportamiento y jerarquía de las excepciones
específicas del dominio de usuarios.
"""

import pytest

from src.modules.user.domain.errors import (
    RepositoryError,
    UserAlreadyExistsError,
    UserDomainError,
    UserNotFoundError,
)


class TestUserDomainErrorHierarchy:
    """Tests para verificar la jerarquía de excepciones del dominio."""

    def test_user_domain_error_is_base_exception(self):
        """Verifica que UserDomainError es la excepción base."""
        error = UserDomainError("Test error")
        assert isinstance(error, Exception)
        assert error.message == "Test error"
        assert error.details is None

    def test_user_domain_error_with_details(self):
        """Verifica que UserDomainError puede incluir detalles."""
        details = {"field": "email", "value": "invalid"}
        error = UserDomainError("Test error", details=details)

        assert error.message == "Test error"
        assert error.details == details
        assert str(error) == "Test error"

    def test_user_not_found_error_inherits_from_base(self):
        """Verifica que UserNotFoundError hereda de UserDomainError."""
        error = UserNotFoundError("User not found")

        assert isinstance(error, UserDomainError)
        assert error.message == "User not found"

    def test_user_already_exists_error_inherits_from_base(self):
        """Verifica que UserAlreadyExistsError hereda de UserDomainError."""
        error = UserAlreadyExistsError("User already exists")

        assert isinstance(error, UserDomainError)
        assert error.message == "User already exists"

    def test_repository_error_inherits_from_base(self):
        """Verifica que RepositoryError hereda de UserDomainError."""
        error = RepositoryError("Repository error")

        assert isinstance(error, UserDomainError)
        assert error.message == "Repository error"


class TestExceptionBehavior:
    """Tests para verificar el comportamiento específico de las excepciones."""

    def test_exceptions_can_be_raised_and_caught(self):
        """Verifica que las excepciones pueden ser lanzadas y capturadas."""
        with pytest.raises(UserNotFoundError) as exc_info:
            raise UserNotFoundError("Test not found error")

        assert exc_info.value.message == "Test not found error"

    def test_specific_exceptions_can_be_caught_as_base(self):
        """Verifica que las excepciones específicas se pueden capturar como base."""
        with pytest.raises(UserDomainError):
            raise UserNotFoundError("User not found")

    def test_repository_exceptions_can_be_caught_as_repository_error(self):
        """Verifica que excepciones de repositorio se pueden capturar como RepositoryError."""
        with pytest.raises(RepositoryError):
            raise RepositoryError("Connection failed")

    def test_exception_with_complex_details(self):
        """Verifica que las excepciones pueden manejar detalles complejos."""
        details = {
            "validation_errors": ["email format", "password strength"],
            "user_input": {"email": "invalid-email", "password": "123"},
            "timestamp": "2025-11-01T10:00:00Z",
        }

        error = UserDomainError("Multiple validation errors", details=details)

        assert error.details["validation_errors"] == [
            "email format",
            "password strength",
        ]
        assert error.details["user_input"]["email"] == "invalid-email"
        assert "timestamp" in error.details


class TestExceptionMessages:
    """Tests para verificar que los mensajes de excepción son apropiados."""

    def test_user_not_found_error_message(self):
        """Verifica mensaje apropiado para UserNotFoundError."""
        user_id = "user_123"
        error = UserNotFoundError(f"User with id {user_id} not found")

        assert "User with id user_123 not found" in str(error)

    def test_user_already_exists_error_message(self):
        """Verifica mensaje apropiado para UserAlreadyExistsError."""
        email = "test@example.com"
        error = UserAlreadyExistsError(f"User with email {email} already exists")

        assert "User with email test@example.com already exists" in str(error)


class TestExceptionCatchingScenarios:
    """Tests para escenarios realistas de captura de excepciones."""

    def test_catch_any_user_domain_error(self):
        """Verifica captura de cualquier error del dominio de usuarios."""
        domain_errors = [
            UserNotFoundError("Not found"),
            UserAlreadyExistsError("Already exists"),
            RepositoryError("Repository error"),
        ]

        for error in domain_errors:
            with pytest.raises(UserDomainError):
                raise error

    def test_specific_error_handling_workflow(self):
        """Verifica un flujo realista de manejo de errores específicos."""

        def simulate_repository_operation():
            # Simula diferentes tipos de errores que pueden ocurrir
            import random

            error_type = random.choice([1, 2, 3])

            if error_type == 1:
                raise UserNotFoundError("User not found")
            if error_type == 2:
                raise UserAlreadyExistsError("Email already registered")
            raise RepositoryError("Database unavailable")

        # Debe poder capturar y clasificar diferentes errores
        with pytest.raises((UserNotFoundError, UserAlreadyExistsError, RepositoryError)):
            simulate_repository_operation()
