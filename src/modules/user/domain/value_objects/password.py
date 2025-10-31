"""Password Value Object."""
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.modules.user.domain.services.password_hasher import PasswordHasher


@dataclass(frozen=True)
class Password:
    """Password as a Value Object.
    
    Represents a hashed password. Never stores passwords in plain text.
    The hashed value is immutable to ensure security.
    """
    
    hashed_value: str
    
    # Password requirements
    MIN_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    
    @classmethod
    async def create(cls, plain_password: str, hasher: "PasswordHasher") -> "Password":
        """Create a Password instance from plain text.
        
        Args:
            plain_password: The password in plain text
            hasher: Password hashing service
            
        Returns:
            Password: Password value object with hashed value
            
        Raises:
            ValueError: If password doesn't meet requirements
        """
        cls._validate_password_strength(plain_password)
        hashed = await hasher.hash(plain_password)
        return cls(hashed_value=hashed)
    
    @classmethod
    def from_hash(cls, hashed_password: str) -> "Password":
        """Create a Password instance from an already hashed value.
        
        This is used when loading a user from the database.
        
        Args:
            hashed_password: Already hashed password
            
        Returns:
            Password: Password value object
        """
        return cls(hashed_value=hashed_password)
    
    @classmethod
    def _validate_password_strength(cls, plain_password: str) -> None:
        """Validate password strength requirements.
        
        Args:
            plain_password: Password to validate
            
        Raises:
            ValueError: If password doesn't meet requirements
        """
        if not plain_password:
            raise ValueError("Password cannot be empty")
        
        if len(plain_password) < cls.MIN_LENGTH:
            raise ValueError(f"Password must be at least {cls.MIN_LENGTH} characters long")
        
        if cls.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', plain_password):
            raise ValueError("Password must contain at least one uppercase letter")
        
        if cls.REQUIRE_LOWERCASE and not re.search(r'[a-z]', plain_password):
            raise ValueError("Password must contain at least one lowercase letter")
        
        if cls.REQUIRE_DIGIT and not re.search(r'\d', plain_password):
            raise ValueError("Password must contain at least one digit")
    
    async def verify(self, plain_password: str, hasher: "PasswordHasher") -> bool:
        """Verify if a plain password matches this hashed password.
        
        Args:
            plain_password: Password to verify
            hasher: Password hashing service
            
        Returns:
            bool: True if password matches, False otherwise
        """
        return await hasher.verify(plain_password, self.hashed_value)
    
    def get_value(self) -> str:
        """Get the hashed password value.
        
        Returns:
            str: The hashed password
        """
        return self.hashed_value
    
    def __str__(self) -> str:
        return "********"  # Never expose password, even hashed
    
    def __repr__(self) -> str:
        return "Password(***)"