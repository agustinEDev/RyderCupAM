"""Email Value Object."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Email:
    """Email address as a Value Object.
    
    Ensures that email addresses are valid and normalized.
    Immutable to guarantee consistency.
    """
    
    value: str
    
    # RFC 5322 simplified regex pattern
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    MAX_LENGTH = 254
    
    def __post_init__(self) -> None:
        """Validate email after initialization.
        
        Raises:
            ValueError: If email format is invalid or too long
        """
        if not self.value:
            raise ValueError("Email cannot be empty")
        
        if len(self.value) > self.MAX_LENGTH:
            raise ValueError(f"Email cannot exceed {self.MAX_LENGTH} characters")
        
        # Normalize to lowercase
        normalized = self.value.lower().strip()
        
        if not self.EMAIL_PATTERN.match(normalized):
            raise ValueError(f"Invalid email format: {self.value}")
        
        # Update value through __dict__ since dataclass is frozen
        object.__setattr__(self, 'value', normalized)
    
    @classmethod
    def create(cls, email: str) -> "Email":
        """Factory method to create an Email instance.
        
        Args:
            email: Email address string
            
        Returns:
            Email: Email value object instance
            
        Raises:
            ValueError: If email is invalid
        """
        return cls(value=email)
    
    def get_domain(self) -> str:
        """Extract the domain part of the email.
        
        Returns:
            str: Domain portion of the email
        """
        return self.value.split('@')[1]
    
    def get_local_part(self) -> str:
        """Extract the local part of the email (before @).
        
        Returns:
            str: Local portion of the email
        """
        return self.value.split('@')[0]
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"Email({self.value})"