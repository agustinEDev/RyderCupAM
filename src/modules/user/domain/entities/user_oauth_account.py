"""
User OAuth Account Entity - Domain Layer

Representa una cuenta OAuth vinculada a un usuario del sistema.
"""

from datetime import UTC, datetime

from src.shared.domain.events.domain_event import DomainEvent

from ..events.google_account_linked_event import GoogleAccountLinkedEvent
from ..value_objects.oauth_account_id import OAuthAccountId
from ..value_objects.oauth_provider import OAuthProvider
from ..value_objects.user_id import UserId


class UserOAuthAccount:
    """
    Entidad que representa una cuenta OAuth vinculada a un usuario.

    Cada usuario puede tener una cuenta OAuth por proveedor (ej: una de Google).
    La entidad almacena el ID del proveedor para identificar al usuario en ese sistema.

    Attributes:
        id: Identificador único del registro
        user_id: Referencia al usuario del sistema
        provider: Proveedor OAuth (GOOGLE, etc.)
        provider_user_id: ID del usuario en el proveedor
        provider_email: Email del usuario en el proveedor
        created_at: Timestamp de vinculación
    """

    def __init__(
        self,
        id: OAuthAccountId | None,
        user_id: UserId,
        provider: OAuthProvider,
        provider_user_id: str,
        provider_email: str,
        created_at: datetime | None = None,
        domain_events: list[DomainEvent] | None = None,
    ):
        self._id = id or OAuthAccountId.generate()
        self._user_id = user_id
        self._provider = provider
        self._provider_user_id = provider_user_id
        self._provider_email = provider_email
        self._created_at = created_at or datetime.now(UTC)
        self._domain_events = domain_events or []

    # === Read-only Properties ===

    @property
    def id(self) -> OAuthAccountId:
        return self._id

    @property
    def user_id(self) -> UserId:
        return self._user_id

    @property
    def provider(self) -> OAuthProvider:
        return self._provider

    @property
    def provider_user_id(self) -> str:
        return self._provider_user_id

    @property
    def provider_email(self) -> str:
        return self._provider_email

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @classmethod
    def create(
        cls,
        user_id: UserId,
        provider: OAuthProvider,
        provider_user_id: str,
        provider_email: str,
    ) -> "UserOAuthAccount":
        """
        Factory method para vincular una nueva cuenta OAuth.

        Args:
            user_id: ID del usuario del sistema
            provider: Proveedor OAuth
            provider_user_id: ID del usuario en el proveedor
            provider_email: Email del usuario en el proveedor

        Returns:
            UserOAuthAccount con evento GoogleAccountLinkedEvent emitido
        """
        account = cls(
            id=OAuthAccountId.generate(),
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            provider_email=provider_email,
            created_at=datetime.now(UTC),
        )

        account._add_domain_event(
            GoogleAccountLinkedEvent(
                user_id=str(user_id.value),
                provider=provider.value,
                provider_email=provider_email,
                linked_at=account._created_at,
            )
        )

        return account

    # === Domain Events ===

    def _add_domain_event(self, event: DomainEvent) -> None:
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        self._domain_events.append(event)

    def get_domain_events(self) -> list[DomainEvent]:
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        return self._domain_events.copy()

    def clear_domain_events(self) -> None:
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        self._domain_events.clear()

    def has_domain_events(self) -> bool:
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        return len(self._domain_events) > 0

    def __str__(self) -> str:
        return (
            f"UserOAuthAccount(id={self.id}, user_id={self.user_id}, "
            f"provider={self.provider}, provider_email={self.provider_email})"
        )

    def __repr__(self) -> str:
        return self.__str__()
