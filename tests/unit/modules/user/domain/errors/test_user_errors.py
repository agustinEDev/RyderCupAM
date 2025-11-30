"""
Tests para User Domain Errors - Verificación de excepciones

Tests que verifican el comportamiento y jerarquía de las excepciones
específicas del dominio de usuarios.
"""

import pytest

from src.modules.user.domain.errors import (
    RepositoryConnectionError,
    RepositoryError,
    RepositoryOperationError,
    RepositoryTimeoutError,
    UserAlreadyExistsError,
    UserDomainError,
    UserNotFoundError,
    UserValidationError,
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

    def test_user_validation_error_inherits_from_base(self):
        """Verifica que UserValidationError hereda de UserDomainError."""
        error = UserValidationError("Validation failed")

        assert isinstance(error, UserDomainError)
        assert isinstance(error, Exception)
        assert error.message == "Validation failed"

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

    def test_repository_connection_error_inherits_from_repository_error(self):
        """Verifica que RepositoryConnectionError hereda de RepositoryError."""
        error = RepositoryConnectionError("Connection failed")

        assert isinstance(error, RepositoryError)
        assert isinstance(error, UserDomainError)
        assert error.message == "Connection failed"

    def test_repository_operation_error_inherits_from_repository_error(self):
        """Verifica que RepositoryOperationError hereda de RepositoryError."""
        error = RepositoryOperationError("Operation failed")

        assert isinstance(error, RepositoryError)
        assert isinstance(error, UserDomainError)
        assert error.message == "Operation failed"

    def test_repository_timeout_error_inherits_from_repository_error(self):
        """Verifica que RepositoryTimeoutError hereda de RepositoryError."""
        error = RepositoryTimeoutError("Operation timed out")

        assert isinstance(error, RepositoryError)
        assert isinstance(error, UserDomainError)
        assert error.message == "Operation timed out"


class TestExceptionBehavior:
    """Tests para verificar el comportamiento específico de las excepciones."""

    def test_exceptions_can_be_raised_and_caught(self):
        """Verifica que las excepciones pueden ser lanzadas y capturadas."""
        with pytest.raises(UserValidationError) as exc_info:
            raise UserValidationError("Test validation error")

        assert exc_info.value.message == "Test validation error"

    def test_specific_exceptions_can_be_caught_as_base(self):
        """Verifica que las excepciones específicas se pueden capturar como base."""
        with pytest.raises(UserDomainError):
            raise UserNotFoundError("User not found")

    def test_repository_exceptions_can_be_caught_as_repository_error(self):
        """Verifica que excepciones de repositorio se pueden capturar como RepositoryError."""
        with pytest.raises(RepositoryError):
            raise RepositoryConnectionError("Connection failed")

    def test_exception_with_complex_details(self):
        """Verifica que las excepciones pueden manejar detalles complejos."""
        details = {
            "validation_errors": ["email format", "password strength"],
            "user_input": {"email": "invalid-email", "password": "123"},
            "timestamp": "2025-11-01T10:00:00Z"
        }

        error = UserValidationError("Multiple validation errors", details=details)

        assert error.details["validation_errors"] == ["email format", "password strength"]
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

    def test_repository_connection_error_message(self):
        """Verifica mensaje apropiado para RepositoryConnectionError."""
        error = RepositoryConnectionError("Cannot connect to database server")

        assert "Cannot connect to database server" in str(error)

    def test_repository_operation_error_message(self):
        """Verifica mensaje apropiado para RepositoryOperationError."""
        error = RepositoryOperationError("Failed to save user: constraint violation")

        assert "Failed to save user: constraint violation" in str(error)

    def test_repository_timeout_error_message(self):
        """Verifica mensaje apropiado para RepositoryTimeoutError."""
        error = RepositoryTimeoutError("Query exceeded 30 second timeout")

        assert "Query exceeded 30 second timeout" in str(error)


class TestExceptionCatchingScenarios:
    """Tests para escenarios realistas de captura de excepciones."""

    def test_catch_any_repository_error(self):
        """Verifica captura de cualquier error de repositorio."""
        repository_errors = [
            RepositoryConnectionError("Connection lost"),
            RepositoryOperationError("Constraint violation"),
            RepositoryTimeoutError("Query timeout"),
            RepositoryError("Generic repository error")
        ]

        for error in repository_errors:
            with pytest.raises(RepositoryError):
                raise error

    def test_catch_any_user_domain_error(self):
        """Verifica captura de cualquier error del dominio de usuarios."""
        domain_errors = [
            UserValidationError("Validation failed"),
            UserNotFoundError("Not found"),
            UserAlreadyExistsError("Already exists"),
            RepositoryError("Repository error")
        ]

        for error in domain_errors:
            with pytest.raises(UserDomainError):
                raise error

    def test_specific_error_handling_workflow(self):
        """Verifica un flujo realista de manejo de errores específicos."""
        def simulate_repository_operation():
            # Simula diferentes tipos de errores que pueden ocurrir
            import random
            error_type = random.choice([1, 2, 3, 4])

            if error_type == 1:
                raise UserNotFoundError("User not found")
            if error_type == 2:
                raise UserAlreadyExistsError("Email already registered")
            if error_type == 3:
                raise RepositoryConnectionError("Database unavailable")
            raise RepositoryTimeoutError("Operation timeout")

        # Debe poder capturar y clasificar diferentes errores
        with pytest.raises((UserNotFoundError, UserAlreadyExistsError, RepositoryError)):
            simulate_repository_operation()
