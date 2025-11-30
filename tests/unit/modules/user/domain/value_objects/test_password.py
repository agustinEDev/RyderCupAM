import bcrypt
import pytest

from src.modules.user.domain.value_objects.password import InvalidPasswordError, Password


class TestPasswordCreation:
    """Tests para la creación de objetos Password"""

    def test_create_password_from_valid_plain_text(self):
        """Debe crear un Password desde texto plano válido"""
        password = Password.from_plain_text("MySecure123")

        # Verificar que se creó correctamente
        assert isinstance(password.hashed_value, str)
        assert password.hashed_value != "MySecure123"  # No debe almacenar texto plano
        assert len(password.hashed_value) > 0

    def test_create_password_with_bcrypt_hash(self):
        """Debe crear un Password con hash bcrypt válido"""
        # Crear hash manualmente
        plain_text = "MySecure123"
        salt = bcrypt.gensalt()
        expected_hash = bcrypt.hashpw(plain_text.encode('utf-8'), salt).decode('utf-8')

        password = Password(expected_hash)
        assert password.hashed_value == expected_hash

    def test_different_passwords_have_different_hashes(self):
        """Passwords iguales deben tener hashes diferentes debido al salt"""
        password1 = Password.from_plain_text("MySecure123")
        password2 = Password.from_plain_text("MySecure123")

        # Aunque el texto plano sea igual, los hashes deben ser diferentes por el salt
        assert password1.hashed_value != password2.hashed_value


class TestPasswordValidation:
    """Tests para la validación de passwords"""

    def test_empty_password_raises_error(self):
        """Password vacío debe lanzar InvalidPasswordError"""
        with pytest.raises(InvalidPasswordError, match="Password no cumple requisitos de seguridad"):
            Password.from_plain_text("")

    def test_none_password_raises_error(self):
        """Password None debe lanzar InvalidPasswordError"""
        with pytest.raises(InvalidPasswordError, match="Password no cumple requisitos de seguridad"):
            Password.from_plain_text(None)

    def test_short_password_raises_error(self):
        """Password menor a 8 caracteres debe lanzar InvalidPasswordError"""
        with pytest.raises(InvalidPasswordError, match="Password no cumple requisitos de seguridad"):
            Password.from_plain_text("Short1")

    def test_password_without_uppercase_raises_error(self):
        """Password sin mayúsculas debe lanzar InvalidPasswordError"""
        with pytest.raises(InvalidPasswordError, match="Password no cumple requisitos de seguridad"):
            Password.from_plain_text("mysecure123")

    def test_password_without_lowercase_raises_error(self):
        """Password sin minúsculas debe lanzar InvalidPasswordError"""
        with pytest.raises(InvalidPasswordError, match="Password no cumple requisitos de seguridad"):
            Password.from_plain_text("MYSECURE123")

    def test_password_without_digit_raises_error(self):
        """Password sin números debe lanzar InvalidPasswordError"""
        with pytest.raises(InvalidPasswordError, match="Password no cumple requisitos de seguridad"):
            Password.from_plain_text("MySecurePass")

    def test_valid_password_formats(self):
        """Debe aceptar diferentes formatos válidos de password"""
        valid_passwords = [
            "MySecure123",
            "Password1",
            "StrongPass99",
            "ComplexP@ss1",
            "VeryLongPassword123",
        ]

        for valid_password in valid_passwords:
            password = Password.from_plain_text(valid_password)
            assert isinstance(password, Password)


class TestPasswordVerification:
    """Tests para la verificación de passwords"""

    def test_verify_correct_password_returns_true(self):
        """Verificar password correcto debe retornar True"""
        plain_text = "MySecure123"
        password = Password.from_plain_text(plain_text)

        assert password.verify(plain_text) is True

    def test_verify_incorrect_password_returns_false(self):
        """Verificar password incorrecto debe retornar False"""
        password = Password.from_plain_text("MySecure123")

        assert password.verify("WrongPassword1") is False

    def test_verify_empty_password_returns_false(self):
        """Verificar password vacío debe retornar False"""
        password = Password.from_plain_text("MySecure123")

        assert password.verify("") is False

    def test_verify_none_password_returns_false(self):
        """Verificar password None debe retornar False"""
        password = Password.from_plain_text("MySecure123")

        assert password.verify(None) is False

    def test_verify_with_invalid_hash_returns_false(self):
        """Verificar con hash inválido debe retornar False"""
        password = Password("invalid-hash")

        assert password.verify("MySecure123") is False


class TestPasswordComparison:
    """Tests para comparación de objetos Password"""

    def test_passwords_with_same_hash_are_equal(self):
        """Passwords con el mismo hash deben ser iguales"""
        hash_value = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"
        password1 = Password(hash_value)
        password2 = Password(hash_value)

        assert password1 == password2

    def test_passwords_with_different_hashes_are_not_equal(self):
        """Passwords con hashes diferentes no deben ser iguales"""
        password1 = Password.from_plain_text("MySecure123")
        password2 = Password.from_plain_text("MySecure123")

        # Aunque el texto plano sea igual, los hashes son diferentes por el salt
        assert password1 != password2

    def test_password_not_equal_to_other_types(self):
        """Password no debe ser igual a otros tipos"""
        password = Password.from_plain_text("MySecure123")

        assert password != "MySecure123"
        assert password != 123
        assert password is not None


class TestPasswordImmutability:
    """Tests para verificar inmutabilidad del Password"""

    def test_password_hash_cannot_be_modified(self):
        """El hash del password no debe poder modificarse después de la creación"""
        password = Password.from_plain_text("MySecure123")

        with pytest.raises(AttributeError):
            password.hashed_value = "new-hash"


class TestPasswordStringRepresentation:
    """Tests para la representación en string del Password"""

    def test_password_str_hides_hash(self):
        """str(password) debe ocultar el hash por seguridad"""
        password = Password.from_plain_text("MySecure123")

        assert str(password) == "[Password Hash]"
        assert password.hashed_value not in str(password)

    def test_password_repr_contains_class_info(self):
        """repr(password) debe contener información de la clase"""
        password = Password.from_plain_text("MySecure123")
        repr_str = repr(password)

        assert "Password" in repr_str
        assert "hashed_value" in repr_str
        # El hash debe estar presente en repr para debugging
        assert password.hashed_value in repr_str


class TestPasswordStrengthValidation:
    """Tests específicos para validación de fortaleza"""

    def test_minimum_length_requirement(self):
        """Password debe tener al menos 8 caracteres"""
        # 7 caracteres - inválido
        with pytest.raises(InvalidPasswordError):
            Password.from_plain_text("Short1A")

        # 8 caracteres - válido
        password = Password.from_plain_text("Valid1A8")
        assert isinstance(password, Password)

    def test_complexity_requirements(self):
        """Password debe cumplir requisitos de complejidad"""
        # Solo minúsculas y números
        with pytest.raises(InvalidPasswordError):
            Password.from_plain_text("lowercase123")

        # Solo mayúsculas y números
        with pytest.raises(InvalidPasswordError):
            Password.from_plain_text("UPPERCASE123")

        # Solo letras sin números
        with pytest.raises(InvalidPasswordError):
            Password.from_plain_text("OnlyLetters")

        # Cumple todos los requisitos
        password = Password.from_plain_text("ValidPass123")
        assert isinstance(password, Password)
