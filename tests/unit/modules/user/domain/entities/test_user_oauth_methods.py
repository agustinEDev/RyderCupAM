"""
Tests unitarios para los métodos OAuth de la entidad User.

Este archivo contiene tests que verifican:
- create_from_oauth() factory method
- has_password() para usuarios OAuth vs normales
- is_valid() para usuarios OAuth sin password
- record_login() con método Google
"""

from datetime import datetime

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.events.user_registered_event import UserRegisteredEvent
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

    def test_create_from_oauth_emits_registered_event(self):
        """
        Test: create_from_oauth() emite UserRegisteredEvent
        Given: Datos de usuario OAuth
        When: Se llama a create_from_oauth()
        Then: Emite evento de registro
        """
        # Arrange & Act
        user = User.create_from_oauth(
            first_name="Bob",
            last_name="Johnson",
            email_str="bob.johnson@gmail.com",
        )

        # Assert
        events = user.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], UserRegisteredEvent)
        assert events[0].email == "bob.johnson@gmail.com"

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
    """Tests para el método has_password()"""

    def test_has_password_true_for_normal_user(self):
        """
        Test: has_password() retorna True para usuarios normales
        Given: Usuario creado con password
        When: Se verifica has_password()
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
        assert user.has_password() is True

    def test_has_password_false_for_oauth_user(self):
        """
        Test: has_password() retorna False para usuarios OAuth
        Given: Usuario creado desde OAuth (sin password)
        When: Se verifica has_password()
        Then: Retorna False
        """
        # Arrange
        user = User.create_from_oauth(
            first_name="OAuth",
            last_name="User",
            email_str="oauth@gmail.com",
        )

        # Act & Assert
        assert user.has_password() is False


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


class TestUserRecordLoginOAuth:
    """Tests para record_login() con método OAuth"""

    def test_record_login_with_google_method(self):
        """
        Test: record_login() acepta login_method="google"
        Given: Usuario OAuth
        When: Se registra login con método "google"
        Then: Evento UserLoggedInEvent se emite con login_method correcto
        """
        # Arrange
        user = User.create_from_oauth(
            first_name="Login",
            last_name="Test",
            email_str="login.test@gmail.com",
        )
        user.clear_domain_events()  # Limpiar evento de registro

        # Act
        user.record_login(
            logged_in_at=datetime.now(),
            ip_address="192.168.1.100",
            user_agent="Chrome/120.0",
            session_id="session-123",
            login_method="google",
        )

        # Assert
        events = user.get_domain_events()
        assert len(events) == 1
        assert events[0].login_method == "google"

    def test_record_login_default_email_method(self):
        """
        Test: record_login() usa "email" como método por defecto
        Given: Usuario normal
        When: Se registra login sin especificar método
        Then: login_method es "email" por defecto
        """
        # Arrange
        user = User.create(
            first_name="Default",
            last_name="Method",
            email_str="default@example.com",
            plain_password="Password123!",
        )
        user.clear_domain_events()

        # Act
        user.record_login(
            logged_in_at=datetime.now(),
            ip_address="192.168.1.101",
        )

        # Assert
        events = user.get_domain_events()
        assert len(events) == 1
        assert events[0].login_method == "email"
