"""
Tests unitarios para los métodos OAuth de la entidad User.

Este archivo contiene tests que verifican:
- create_from_oauth() factory method
- has_password para usuarios OAuth vs normales
- is_valid() para usuarios OAuth sin password
"""

from src.modules.user.domain.entities.user import User
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender


class TestUserCreateFromOAuth:
    """Tests para el factory method create_from_oauth()"""

    def test_create_from_oauth_creates_user_without_password(self):
        """
        Test: create_from_oauth() crea usuario sin password
        Given: Datos de usuario OAuth (sin password)
        When: Se llama a create_from_oauth()
        Then: Usuario creado con password=None
        """
        # Arrange
        first_name = "John"
        last_name = "Doe"
        email_str = "john.doe@gmail.com"

        # Act
        user = User.create_from_oauth(
            first_name=first_name,
            last_name=last_name,
            email_str=email_str,
        )

        # Assert
        assert user.password is None
        assert user.first_name == first_name
        assert user.last_name == last_name
        assert str(user.email) == email_str

    def test_create_from_oauth_email_is_verified(self):
        """
        Test: create_from_oauth() marca email como verificado
        Given: Usuario creado desde OAuth
        When: Se verifica email_verified
        Then: email_verified es True (Google ya verificó el email)
        """
        # Arrange & Act
        user = User.create_from_oauth(
            first_name="Jane",
            last_name="Smith",
            email_str="jane.smith@gmail.com",
        )

        # Assert
        assert user.email_verified is True

    def test_create_from_oauth_with_country_code(self):
        """
        Test: create_from_oauth() acepta country_code opcional
        Given: Usuario OAuth con country_code
        When: Se crea usuario
        Then: country_code se establece correctamente
        """
        # Arrange & Act
        user = User.create_from_oauth(
            first_name="Maria",
            last_name="Garcia",
            email_str="maria.garcia@gmail.com",
            country_code_str="ES",
        )

        # Assert
        assert user.country_code is not None
        assert isinstance(user.country_code, CountryCode)
        assert str(user.country_code) == "ES"

    def test_create_from_oauth_with_gender(self):
        """
        Test: create_from_oauth() acepta gender opcional
        Given: Usuario OAuth con gender
        When: Se crea usuario
        Then: gender se establece correctamente
        """
        # Arrange & Act
        user = User.create_from_oauth(
            first_name="Alex",
            last_name="Taylor",
            email_str="alex.taylor@gmail.com",
            gender=Gender.MALE,
        )

        # Assert
        assert user.gender == Gender.MALE


class TestUserHasPassword:
    """Tests para la propiedad has_password"""

    def test_has_password_true_for_normal_user(self):
        """
        Test: has_password retorna True para usuarios normales
        Given: Usuario creado con password
        When: Se verifica has_password
        Then: Retorna True
        """
        # Arrange
        user = User.create(
            first_name="Normal",
            last_name="User",
            email_str="normal@example.com",
            plain_password="SecurePassword123!",
        )

        # Act & Assert
        assert user.has_password is True

    def test_has_password_false_for_oauth_user(self):
        """
        Test: has_password retorna False para usuarios OAuth
        Given: Usuario creado desde OAuth (sin password)
        When: Se verifica has_password
        Then: Retorna False
        """
        # Arrange
        user = User.create_from_oauth(
            first_name="OAuth",
            last_name="User",
            email_str="oauth@gmail.com",
        )

        # Act & Assert
        assert user.has_password is False


class TestUserIsValidOAuth:
    """Tests para is_valid() con usuarios OAuth"""

    def test_is_valid_true_for_oauth_user_without_password(self):
        """
        Test: is_valid() retorna True para usuario OAuth sin password
        Given: Usuario OAuth válido (email, nombre, apellido)
        When: Se verifica is_valid()
        Then: Retorna True aunque no tenga password
        """
        # Arrange
        user = User.create_from_oauth(
            first_name="Valid",
            last_name="OAuthUser",
            email_str="valid.oauth@gmail.com",
        )

        # Act & Assert
        assert user.is_valid() is True


class TestClaimWithVerifiedOAuth:
    """Un proveedor que verificó el correo se queda una cuenta sin verificar (G1, G3)."""

    def _cuenta(self, verificada: bool) -> User:
        user = User.create(
            first_name="Ana",
            last_name="Dueña",
            email_str="ana@example.com",
            plain_password="SecureP@ssw0rd123!",
        )
        user.generate_verification_token()
        if verificada:
            user.confirm_email_ownership()
        return user

    def test_an_unverified_account_loses_its_unproven_password(self):
        """
        Given: Una cuenta con contraseña y el correo sin verificar (la pudo crear cualquiera)
        When: Google, que verificó ese correo, se la queda
        Then: True; sin contraseña, verificada y sin token de verificación pendiente
        """
        user = self._cuenta(verificada=False)

        assert user.claim_with_verified_oauth() is True

        assert not user.has_password
        assert user.email_verified
        assert user.verification_token is None

    def test_a_pending_password_reset_is_dropped_too(self):
        """
        Given: Una cuenta sin verificar con un «Olvidé mi contraseña» pedido antes
        When: Google se la queda
        Then: El token de restablecer, fuera: es de antes del cambio de manos
        """
        user = self._cuenta(verificada=False)
        user.generate_password_reset_token()

        user.claim_with_verified_oauth()

        assert user.password_reset_token is None

    def test_a_verified_account_is_left_as_it_is(self):
        """
        Given: Una cuenta ya verificada, con contraseña
        When: Se intenta quedar con ella un proveedor
        Then: False y conserva la contraseña: ya se demostró que es del dueño del correo
        """
        user = self._cuenta(verificada=True)

        assert user.claim_with_verified_oauth() is False

        assert user.has_password
        assert user.verify_password("SecureP@ssw0rd123!")

    def test_the_owner_can_set_a_password_afterwards(self):
        """
        Given: Una cuenta que se quedó sin contraseña así
        When: El dueño la pone con «Olvidé mi contraseña» (G6)
        Then: Entra con la nueva
        """
        user = self._cuenta(verificada=False)
        user.claim_with_verified_oauth()
        token = user.generate_password_reset_token()

        user.reset_password(token, "OtraClave#2026segura")

        assert user.verify_password("OtraClave#2026segura")
