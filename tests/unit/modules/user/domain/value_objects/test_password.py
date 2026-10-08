import bcrypt
import pytest

from src.modules.user.domain.value_objects.password import (
    InvalidPasswordError,
    Password,
)


class TestPasswordCreation:
    """Tests para la creación de objetos Password"""

    def test_create_password_from_valid_plain_text(self):
        """Debe crear un Password desde texto plano válido (12+ chars, complejidad completa)"""
        password = Password.from_plain_text("MyS3cur3P@ss!")

        # Verificar que se creó correctamente
        assert isinstance(password.hashed_value, str)
        assert password.hashed_value != "MyS3cur3P@ss!"  # No debe almacenar texto plano
        assert len(password.hashed_value) > 0

    def test_create_password_with_bcrypt_hash(self):
        """Debe crear un Password con hash bcrypt válido"""
        # Crear hash manualmente
        plain_text = "MyS3cur3P@ss!"
        salt = bcrypt.gensalt()
        expected_hash = bcrypt.hashpw(plain_text.encode("utf-8"), salt).decode("utf-8")

        password = Password(expected_hash)
        assert password.hashed_value == expected_hash

    def test_different_passwords_have_different_hashes(self):
        """Passwords iguales deben tener hashes diferentes debido al salt"""
        password1 = Password.from_plain_text("MyS3cur3P@ss!")
        password2 = Password.from_plain_text("MyS3cur3P@ss!")

        # Aunque el texto plano sea igual, los hashes deben ser diferentes por el salt
        assert password1.hashed_value != password2.hashed_value


class TestPasswordValidation:
    """Tests para la validación de passwords (OWASP ASVS V2.1)"""

    def test_empty_password_raises_error(self):
        """Password vacío debe lanzar InvalidPasswordError"""
        with pytest.raises(InvalidPasswordError, match="no puede estar vacía"):
            Password.from_plain_text("")  # type: ignore[arg-type]

    def test_none_password_raises_error(self):
        """Password None debe lanzar InvalidPasswordError"""
        with pytest.raises(InvalidPasswordError):
            Password.from_plain_text(None)  # type: ignore[arg-type]

    def test_short_password_raises_error(self):
        """Password menor a 12 caracteres debe lanzar InvalidPasswordError (OWASP V2.1.1)"""
        # 8 caracteres (era válido antes, ahora NO)
        with pytest.raises(InvalidPasswordError, match="debe tener al menos 12 caracteres"):
            Password.from_plain_text("Short1!A")

        # 11 caracteres (casi)
        with pytest.raises(InvalidPasswordError, match="debe tener al menos 12 caracteres"):
            Password.from_plain_text("Short1!AA")

    def test_password_without_uppercase_raises_error(self):
        """Password sin mayúsculas debe lanzar InvalidPasswordError (OWASP V2.1.2)"""
        with pytest.raises(
            InvalidPasswordError, match="debe contener al menos una letra mayúscula"
        ):
            Password.from_plain_text("mysecure123!")

    def test_password_without_lowercase_raises_error(self):
        """Password sin minúsculas debe lanzar InvalidPasswordError (OWASP V2.1.2)"""
        with pytest.raises(
            InvalidPasswordError, match="debe contener al menos una letra minúscula"
        ):
            Password.from_plain_text("MYSECURE123!")

    def test_password_without_digit_raises_error(self):
        """Password sin números debe lanzar InvalidPasswordError (OWASP V2.1.2)"""
        with pytest.raises(InvalidPasswordError, match="debe contener al menos un número"):
            Password.from_plain_text("MySecurePass!")

    def test_password_without_special_char_raises_error(self):
        """Password sin carácter especial debe lanzar InvalidPasswordError (OWASP V2.1.2)"""
        with pytest.raises(
            InvalidPasswordError, match="debe contener al menos un carácter especial"
        ):
            Password.from_plain_text("MySecurePass123")

    def test_common_password_raises_error(self):
        """Password en blacklist debe lanzar InvalidPasswordError (OWASP V2.1.7)"""
        # NOTA: La blacklist compara exactamente (case-insensitive), no busca substrings
        # Necesitamos contraseñas que estén EXACTAMENTE en la blacklist
        # Pero la longitud mínima es 12 caracteres, así que las cortas (como "password123")
        # fallarán ANTES por longitud, no por blacklist

        # La mayoría de contraseñas comunes tienen < 12 chars, entonces fallan por longitud primero
        # Por ejemplo: "password123" (11 chars) → falla por longitud

        # Este test verifica que el check de blacklist EXISTE (aunque es difícil probar aisladamente)
        # porque las contraseñas comunes son típicamente cortas
        with pytest.raises(InvalidPasswordError):  # Falla por longitud (11 chars)
            Password.from_plain_text("password123")

        with pytest.raises(InvalidPasswordError):  # Falla por longitud (8 chars)
            Password.from_plain_text("password")

    @pytest.mark.parametrize("variante", ["Password123!", "PassWord123!", "pAsSwOrD123!"])
    def test_common_password_that_meets_the_rest_is_rejected_by_the_blacklist(self, variante):
        """
        Given «Password123!» (y sus variantes de mayúsculas), que cumple longitud y complejidad
        When se crea la contraseña
        Then la para la lista negra con su motivo: antes se registraba (BE #518)
        """
        with pytest.raises(InvalidPasswordError, match="demasiado común"):
            Password.from_plain_text(variante)

    def test_valid_password_formats(self):
        """Debe aceptar diferentes formatos válidos de password (12+ chars, complejidad completa)"""
        valid_passwords = [
            "MyS3cur3P@ss!",  # 13 chars, cumple todo
            "Str0ng!P@ssw0rd",  # 15 chars, cumple todo
            "C0mpl3x!tyR0cks",  # 15 chars, cumple todo
            "VeryL0ngP@ssw0rd2025!",  # 21 chars, cumple todo
            "Sup3r$ecur3#2025",  # 16 chars, cumple todo
        ]

        for valid_password in valid_passwords:
            password = Password.from_plain_text(valid_password)
            assert isinstance(password, Password)


class TestPasswordVerification:
    """Tests para la verificación de passwords"""

    def test_verify_correct_password_returns_true(self):
        """Verificar password correcto debe retornar True"""
        plain_text = "MyS3cur3P@ss!"
        password = Password.from_plain_text(plain_text)

        assert password.verify(plain_text) is True

    def test_verify_incorrect_password_returns_false(self):
        """Verificar password incorrecto debe retornar False"""
        password = Password.from_plain_text("MyS3cur3P@ss!")

        assert password.verify("Wr0ngP@ssw0rd!") is False

    def test_verify_empty_password_returns_false(self):
        """Verificar password vacío debe retornar False"""
        password = Password.from_plain_text("MyS3cur3P@ss!")

        assert password.verify("") is False

    def test_verify_none_password_returns_false(self):
        """Verificar password None debe retornar False"""
        password = Password.from_plain_text("MyS3cur3P@ss!")

        assert password.verify(None) is False

    def test_verify_with_invalid_hash_returns_false(self):
        """Verificar con hash inválido debe retornar False"""
        password = Password("invalid-hash")

        assert password.verify("MyS3cur3P@ss!") is False


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
        password1 = Password.from_plain_text("MyS3cur3P@ss!")
        password2 = Password.from_plain_text("MyS3cur3P@ss!")

        # Aunque el texto plano sea igual, los hashes son diferentes por el salt
        assert password1 != password2

    def test_password_not_equal_to_other_types(self):
        """Password no debe ser igual a otros tipos"""
        password = Password.from_plain_text("MyS3cur3P@ss!")

        assert password != "MyS3cur3P@ss!"
        assert password != 123
        assert password is not None


class TestPasswordImmutability:
    """Tests para verificar inmutabilidad del Password"""

    def test_password_hash_cannot_be_modified(self):
        """El hash del password no debe poder modificarse después de la creación"""
        password = Password.from_plain_text("MyS3cur3P@ss!")

        with pytest.raises(AttributeError):
            password.hashed_value = "new-hash"


class TestPasswordStringRepresentation:
    """Tests para la representación en string del Password"""

    def test_password_str_hides_hash(self):
        """str(password) debe ocultar el hash por seguridad"""
        password = Password.from_plain_text("MyS3cur3P@ss!")

        assert str(password) == "[Password Hash]"
        assert password.hashed_value not in str(password)

    def test_password_repr_contains_class_info(self):
        """repr(password) debe contener información de la clase"""
        password = Password.from_plain_text("MyS3cur3P@ss!")
        repr_str = repr(password)

        assert "Password" in repr_str
        assert "hashed_value" in repr_str
        # El hash debe estar presente en repr para debugging
        assert password.hashed_value in repr_str


class TestPasswordStrengthValidation:
    """Tests específicos para validación de fortaleza (OWASP ASVS V2.1)"""

    def test_minimum_length_requirement(self):
        """Password debe tener al menos 12 caracteres (OWASP V2.1.1)"""
        # 11 caracteres - inválido
        with pytest.raises(InvalidPasswordError, match="debe tener al menos 12 caracteres"):
            Password.from_plain_text("Short1!AAaa")

        # 12 caracteres - válido (con complejidad completa)
        password = Password.from_plain_text("V@l1d1234567")
        assert isinstance(password, Password)

    def test_complexity_requirements(self):
        """Password debe cumplir requisitos de complejidad (OWASP V2.1.2)"""
        # Solo minúsculas y números (falta mayúscula y símbolo) - 12+ chars
        with pytest.raises(InvalidPasswordError):
            Password.from_plain_text("lowercase123456")

        # Solo mayúsculas y números (falta minúscula y símbolo) - 12+ chars
        with pytest.raises(InvalidPasswordError):
            Password.from_plain_text("UPPERCASE123456")

        # Solo letras sin números y símbolo - 12+ chars
        with pytest.raises(InvalidPasswordError):
            Password.from_plain_text("OnlyLettersHere")

        # Tiene mayúscula, minúscula, número pero falta símbolo
        with pytest.raises(
            InvalidPasswordError, match="debe contener al menos un carácter especial"
        ):
            Password.from_plain_text("ValidPass1234")

        # Cumple todos los requisitos (12+ chars, upper, lower, digit, symbol)
        password = Password.from_plain_text("V@l1dP@ss123")
        assert isinstance(password, Password)


class TestPasswordLongerThanBcryptLimit:
    """
    bcrypt solo usa los primeros 72 BYTES de la contraseña. Hasta bcrypt 4 los
    recortaba en silencio; bcrypt 5 lanza ValueError si llegan más. La política
    admite hasta 128 CARACTERES, y una eñe ocupa dos bytes: una contraseña válida
    puede superar los 72 bytes con bastante menos de 128 caracteres.
    """

    LARGA = "Aa1!" + "x" * 96  # 100 caracteres ASCII = 100 bytes
    CON_ENES = "Ññ1!" + "ñ" * 40  # 44 caracteres, 88 bytes en UTF-8

    @staticmethod
    def _hash_de_bcrypt_4(plain: str) -> Password:
        """Lo que guardó bcrypt 4 para una contraseña larga: el hash de sus 72 primeros bytes."""
        hashed = bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt(rounds=4))
        return Password(hashed.decode("utf-8"))

    def test_create_and_verify_password_over_72_bytes(self):
        """
        Given: una contraseña válida de 100 caracteres (100 bytes)
        When: se crea el hash y se verifica
        Then: funciona, sin ValueError de bcrypt 5
        """
        password = Password.from_plain_text(self.LARGA)
        assert password.verify(self.LARGA) is True

    def test_create_and_verify_multibyte_password_over_72_bytes(self):
        """
        Given: 44 caracteres con eñes, que son 88 bytes
        When: se crea el hash y se verifica
        Then: funciona
        """
        assert len(self.CON_ENES) < Password.MAX_LENGTH
        assert len(self.CON_ENES.encode("utf-8")) > 72
        password = Password.from_plain_text(self.CON_ENES)
        assert password.verify(self.CON_ENES) is True

    def test_existing_user_with_long_password_can_still_log_in(self):
        """
        Given: el hash que guardó bcrypt 4 para una contraseña de más de 72 bytes
        When: el usuario entra con esa contraseña completa
        Then: se acepta: los hashes existentes siguen valiendo
        """
        guardado = self._hash_de_bcrypt_4(self.LARGA)
        assert guardado.verify(self.LARGA) is True

    def test_wrong_long_password_is_rejected(self):
        """
        Given: una contraseña larga
        When: se verifica otra que difiere dentro de los 72 primeros bytes
        Then: se rechaza
        """
        password = Password.from_plain_text(self.LARGA)
        otra = "Aa2!" + "x" * 96
        assert password.verify(otra) is False

    def test_password_of_exactly_72_bytes(self):
        """
        Given: una contraseña de exactamente 72 bytes
        When: se crea y se verifica
        Then: funciona (el límite no recorta nada)
        """
        exacta = "Aa1!" + "x" * 68
        assert len(exacta.encode("utf-8")) == 72
        password = Password.from_plain_text(exacta)
        assert password.verify(exacta) is True
        assert password.verify(exacta[:-1] + "y") is False

    def test_cut_inside_a_multibyte_character_matches_bcrypt_4(self):
        """
        Given: una contraseña cuyo byte 72 cae a mitad de una eñe, con hash de bcrypt 4
        When: el usuario entra
        Then: se acepta: el recorte es por BYTES, igual que hacía bcrypt 4
        """
        corte = "Aa1!" + "x" * 67 + "ñ" + "zzzz"  # la ñ ocupa los bytes 72 y 73
        assert len(corte.encode("utf-8")[:72].decode("utf-8", errors="ignore")) == 71
        guardado = self._hash_de_bcrypt_4(corte)
        assert guardado.verify(corte) is True


class TestPasswordErrorCodes:
    """BE #519: cada regla de la política lleva su código, para que el cliente la traduzca."""

    @pytest.mark.parametrize(
        ("password", "code"),
        [
            ("", "PASSWORD_EMPTY"),
            (" Abcdefghi1!", "PASSWORD_EDGE_SPACES"),
            ("Abc1!", "PASSWORD_TOO_SHORT"),
            ("A1!" + "a" * 130, "PASSWORD_TOO_LONG"),
            ("abcdefghij1!", "PASSWORD_NO_UPPERCASE"),
            ("ABCDEFGHIJ1!", "PASSWORD_NO_LOWERCASE"),
            ("Abcdefghijk!", "PASSWORD_NO_DIGIT"),
            ("Abcdefghijk1", "PASSWORD_NO_SYMBOL"),
            ("Comun-Segura123!", "PASSWORD_TOO_COMMON"),
        ],
    )
    def test_each_rule_raises_its_own_code(self, password, code, monkeypatch):
        """
        Given una contraseña que solo rompe una regla
        When se crea
        Then el error lleva el código de esa regla, además del mensaje de siempre

        La lista negra se simula: aquí se prueba el código, no la lista (BE #518).
        """
        monkeypatch.setattr(
            "src.modules.user.domain.value_objects.password.is_common_password",
            lambda candidate: candidate == "Comun-Segura123!",
        )
        with pytest.raises(InvalidPasswordError) as error:
            Password.from_plain_text(password)

        assert error.value.error_code == code
        assert str(error.value)
