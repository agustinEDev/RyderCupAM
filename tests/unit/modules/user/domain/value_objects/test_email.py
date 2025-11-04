import pytest
from src.modules.user.domain.value_objects.email import Email, InvalidEmailError


class TestEmailCreation:
    """Tests para la creación de objetos Email"""
    
    def test_create_valid_email(self):
        """Debe crear un Email con una dirección válida"""
        email = Email("test@example.com")
        assert email.value == "test@example.com"
    
    def test_create_email_with_uppercase(self):
        """Debe normalizar email a minúsculas"""
        email = Email("TEST@EXAMPLE.COM")
        assert email.value == "test@example.com"
    
    def test_create_email_with_spaces(self):
        """Debe remover espacios al inicio y final"""
        email = Email("  test@example.com  ")
        assert email.value == "test@example.com"
    
    def test_create_complex_valid_emails(self):
        """Debe crear emails válidos con diferentes formatos permitidos"""
        valid_emails = [
            "user@domain.co.uk",
            "test.email@subdomain.example.org",
            "user+tag@example.com",
            "user_name@example-site.com",
            "a@example.com",  # Un solo carácter antes del @
            "123@example.com",  # Números
        ]
        
        for valid_email in valid_emails:
            email = Email(valid_email.lower())  # Normalizado
            assert email.value == valid_email.lower()


class TestEmailValidation:
    """Tests para la validación de emails"""
    
    def test_empty_email_raises_error(self):
        """Email vacío debe lanzar InvalidEmailError"""
        with pytest.raises(InvalidEmailError, match="El email no puede ser nulo o vacío"):
            Email("")
    
    def test_none_email_raises_error(self):
        """Email None debe lanzar InvalidEmailError"""
        with pytest.raises(InvalidEmailError, match="El email debe ser un string"):
            Email(None)
    
    def test_whitespace_only_email_raises_error(self):
        """Email solo con espacios debe lanzar InvalidEmailError"""
        with pytest.raises(InvalidEmailError, match="El email no puede ser nulo o vacío"):
            Email("   ")
    
    def test_invalid_email_format_raises_error(self):
        """Email con formato inválido debe lanzar InvalidEmailError"""
        invalid_emails = [
            "invalid-email",
            "@example.com",
            "test@",
            "test@example",
            "test@.com",
            "test..test@example.com",
            ".test@example.com",
            "test.@example.com",
            "test@.example.com",
            "test@example.com.",
        ]
        
        for invalid_email in invalid_emails:
            with pytest.raises(InvalidEmailError):
                Email(invalid_email)


class TestEmailComparison:
    """Tests para comparación de objetos Email"""
    
    def test_emails_with_same_value_are_equal(self):
        """Emails con el mismo valor deben ser iguales"""
        email1 = Email("test@example.com")
        email2 = Email("test@example.com")
        assert email1 == email2
    
    def test_emails_with_different_values_are_not_equal(self):
        """Emails con valores diferentes no deben ser iguales"""
        email1 = Email("test1@example.com")
        email2 = Email("test2@example.com")
        assert email1 != email2
    
    def test_email_equality_ignores_original_case(self):
        """La igualdad debe ignorar el caso original"""
        email1 = Email("TEST@EXAMPLE.COM")
        email2 = Email("test@example.com")
        assert email1 == email2


class TestEmailImmutability:
    """Tests para verificar inmutabilidad del Email"""
    
    def test_email_value_cannot_be_modified(self):
        """El valor del email no debe poder modificarse después de la creación"""
        email = Email("test@example.com")
        
        with pytest.raises(AttributeError):
            email.value = "new@example.com"


class TestEmailStringRepresentation:
    """Tests para la representación en string del Email"""
    
    def test_email_str_returns_value(self):
        """str(email) debe retornar el valor del email"""
        email = Email("test@example.com")
        assert str(email) == "test@example.com"
    
    def test_email_repr_contains_class_and_value(self):
        """repr(email) debe contener la clase y el valor"""
        email = Email("test@example.com")
        assert repr(email) == "Email(value='test@example.com')"
