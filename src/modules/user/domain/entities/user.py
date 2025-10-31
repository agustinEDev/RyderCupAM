"""User Entity."""
from datetime import datetime
from typing import TYPE_CHECKING

from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password

if TYPE_CHECKING:
    from src.modules.user.domain.services.password_hasher import PasswordHasher


class User:
    """User aggregate root.
    
    Represents a user in the system with its business rules and behaviors.
    This is a rich domain model that encapsulates business logic.
    """
    
    def __init__(
        self,
        user_id: UserId,
        email: Email,
        password: Password,
        first_name: str,
        last_name: str,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        """Initialize a User entity.
        
        Args:
            user_id: Unique user identifier
            email: User email address
            password: User hashed password
            first_name: User's first name
            last_name: User's last name
            created_at: Creation timestamp
            updated_at: Last update timestamp
        """
        self._id = user_id
        self._email = email
        self._password = password
        self._first_name = first_name
        self._last_name = last_name
        self._created_at = created_at or datetime.now()
        self._updated_at = updated_at or datetime.now()

        self._validate()
    
    @classmethod
    async def create(
        cls,
        email: str,
        plain_password: str,
        first_name: str,
        last_name: str,
        hasher: "PasswordHasher",
    ) -> "User":
        """Factory method to create a new User.
        
        Args:
            email: Email address
            plain_password: Password in plain text
            first_name: User's first name
            last_name: User's last name
            hasher: Password hashing service
            
        Returns:
            User: New user instance
            
        Raises:
            ValueError: If any validation fails
        """
        user_id = UserId.generate()
        email_vo = Email.create(email)
        password_vo = await Password.create(plain_password, hasher)
        
        return cls(
            user_id=user_id,
            email=email_vo,
            password=password_vo,
            first_name=first_name,
            last_name=last_name,
        )
    
    def _validate(self) -> None:
        """Validate user entity invariants.
        
        Raises:
            ValueError: If validation fails
        """
        if not self._first_name or not self._first_name.strip():
            raise ValueError("First name cannot be empty")
        
        if not self._last_name or not self._last_name.strip():
            raise ValueError("Last name cannot be empty")
        
        if len(self._first_name) > 100:
            raise ValueError("First name cannot exceed 100 characters")
        
        if len(self._last_name) > 100:
            raise ValueError("Last name cannot exceed 100 characters")
    
    async def verify_password(
        self, 
        plain_password: str, 
        hasher: "PasswordHasher"
    ) -> bool:
        """Verify if provided password matches user's password.
        
        Args:
            plain_password: Password to verify
            hasher: Password hashing service
            
        Returns:
            bool: True if password matches, False otherwise
        """
        return await self._password.verify(plain_password, hasher)
    
    def update_profile(self, first_name: str, last_name: str) -> None:
        """Update user profile information.
        
        Args:
            first_name: New first name
            last_name: New last name
            
        Raises:
            ValueError: If validation fails
        """
        self._first_name = first_name
        self._last_name = last_name
        self._updated_at = datetime.now()
        self._validate()
    
    def get_full_name(self) -> str:
        """Get user's full name.
        
        Returns:
            str: First name and last name combined
        """
        return f"{self._first_name} {self._last_name}"
    
    # Properties (read-only access to internal state)
    
    @property
    def id(self) -> UserId:
        """User ID."""
        return self._id
    
    @property
    def email(self) -> Email:
        """User email."""
        return self._email
    
    @property
    def password(self) -> Password:
        """User password."""
        return self._password
    
    @property
    def first_name(self) -> str:
        """User first name."""
        return self._first_name
    
    @property
    def last_name(self) -> str:
        """User last name."""
        return self._last_name
    
    @property
    def created_at(self) -> datetime:
        """Creation timestamp."""
        return self._created_at
    
    @property
    def updated_at(self) -> datetime:
        """Last update timestamp."""
        return self._updated_at
    
    def __eq__(self, other: object) -> bool:
        """Check equality based on ID."""
        if not isinstance(other, User):
            return False
        return self._id == other._id
    
    def __hash__(self) -> int:
        """Hash based on ID."""
        return hash(self._id)
    
    def __repr__(self) -> str:
        return f"User(id={self._id}, email={self._email})"