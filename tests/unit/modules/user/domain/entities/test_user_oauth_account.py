"""
Tests unitarios para la entidad UserOAuthAccount.

Este archivo contiene tests que verifican:
- Creación de cuentas OAuth vinculadas
- Factory method create()
- Domain events
- Validaciones
"""

from datetime import datetime

from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.events.google_account_linked_event import (
    GoogleAccountLinkedEvent,
)
from src.modules.user.domain.value_objects.oauth_account_id import OAuthAccountId
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_id import UserId


class TestUserOAuthAccountCreation:
    """Tests para creación de UserOAuthAccount"""

    def test_create_factory_sets_attributes(self):
        """
        Test: El factory method create() establece todos los atributos
        Given: user_id, provider, provider_user_id, provider_email
        When: Se llama a UserOAuthAccount.create()
        Then: La cuenta se crea con todos los atributos correctos
        """
        # Arrange
        user_id = UserId.generate()
        provider = OAuthProvider.GOOGLE
        provider_user_id = "1234567890"
        provider_email = "user@gmail.com"

        # Act
        account = UserOAuthAccount.create(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            provider_email=provider_email,
        )

        # Assert
        assert account.user_id == user_id
        assert account.provider == provider
        assert account.provider_user_id == provider_user_id
        assert account.provider_email == provider_email
        assert isinstance(account.id, OAuthAccountId)
        assert isinstance(account.created_at, datetime)

    def test_create_emits_google_account_linked_event(self):
        """
        Test: create() emite GoogleAccountLinkedEvent
        Given: Parámetros válidos para crear cuenta OAuth
        When: Se llama a create()
        Then: Emite un evento GoogleAccountLinkedEvent
        """
        # Arrange
        user_id = UserId.generate()
        provider_email = "john.doe@gmail.com"

        # Act
        account = UserOAuthAccount.create(
            user_id=user_id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="abc123",
            provider_email=provider_email,
        )

        # Assert
        events = account.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], GoogleAccountLinkedEvent)
        assert events[0].user_id == str(user_id.value)
        assert events[0].provider == "google"
        assert events[0].provider_email == provider_email

    def test_create_generates_unique_id(self):
        """
        Test: create() genera ID único para cada cuenta
        Given: Múltiples llamadas a create()
        When: Se crean varias cuentas OAuth
        Then: Todas tienen IDs únicos
        """
        # Arrange
        user_id = UserId.generate()

        # Act
        accounts = [
            UserOAuthAccount.create(
                user_id=user_id,
                provider=OAuthProvider.GOOGLE,
                provider_user_id=f"user{i}",
                provider_email=f"user{i}@gmail.com",
            )
            for i in range(3)
        ]

        # Assert
        ids = [str(account.id.value) for account in accounts]
        assert len(set(ids)) == 3  # Todos únicos

    def test_init_with_explicit_id(self):
        """
        Test: El constructor acepta un ID explícito
        Given: Un OAuthAccountId explícito
        When: Se crea UserOAuthAccount con ese ID
        Then: La cuenta tiene ese ID específico
        """
        # Arrange
        account_id = OAuthAccountId.generate()
        user_id = UserId.generate()

        # Act
        account = UserOAuthAccount(
            id=account_id,
            user_id=user_id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="explicit_id_user",
            provider_email="explicit@gmail.com",
        )

        # Assert
        assert account.id == account_id

    def test_init_defaults_created_at(self):
        """
        Test: El constructor inicializa created_at por defecto
        Given: Constructor sin created_at explícito
        When: Se crea UserOAuthAccount
        Then: created_at se establece a datetime.now()
        """
        # Arrange
        user_id = UserId.generate()
        before = datetime.now()

        # Act
        account = UserOAuthAccount(
            id=None,
            user_id=user_id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="timestamp_test",
            provider_email="timestamp@gmail.com",
        )

        # Assert
        after = datetime.now()
        assert before <= account.created_at <= after


class TestUserOAuthAccountDomainEvents:
    """Tests para manejo de domain events"""

    def test_domain_events_clear(self):
        """
        Test: clear_domain_events() elimina todos los eventos
        Given: UserOAuthAccount con eventos
        When: Se llama a clear_domain_events()
        Then: get_domain_events() retorna lista vacía
        """
        # Arrange
        user_id = UserId.generate()
        account = UserOAuthAccount.create(
            user_id=user_id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="clear_test",
            provider_email="clear@gmail.com",
        )
        assert account.has_domain_events()

        # Act
        account.clear_domain_events()

        # Assert
        assert not account.has_domain_events()
        assert len(account.get_domain_events()) == 0

    def test_has_domain_events_when_created(self):
        """
        Test: has_domain_events() retorna True después de create()
        Given: UserOAuthAccount recién creado
        When: Se verifica has_domain_events()
        Then: Retorna True
        """
        # Arrange & Act
        user_id = UserId.generate()
        account = UserOAuthAccount.create(
            user_id=user_id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="events_test",
            provider_email="events@gmail.com",
        )

        # Assert
        assert account.has_domain_events() is True


class TestUserOAuthAccountStringRepresentation:
    """Tests para representación string"""

    def test_str_representation(self):
        """
        Test: __str__ contiene información clave
        Given: UserOAuthAccount
        When: Se convierte a string
        Then: Contiene id, user_id, provider, provider_email
        """
        # Arrange
        user_id = UserId.generate()
        account = UserOAuthAccount.create(
            user_id=user_id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="str_test",
            provider_email="str@gmail.com",
        )

        # Act
        str_representation = str(account)

        # Assert
        assert "UserOAuthAccount" in str_representation
        assert str(account.id) in str_representation
        assert str(user_id) in str_representation
        assert "google" in str_representation
        assert "str@gmail.com" in str_representation
