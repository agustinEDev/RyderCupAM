"""Password Hasher Domain Service Interface."""
from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    """Abstract interface for password hashing operations.
    
    This is a domain service interface that defines the contract
    for password hashing implementations. The actual implementation
    will be in the infrastructure layer.
    """
    
    @abstractmethod
    async def hash(self, plain_password: str) -> str:
        """Hash a plain text password.
        
        Args:
            plain_password: The password in plain text
            
        Returns:
            str: The hashed password
        """
        pass
    
    @abstractmethod
    async def verify(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed password.
        
        Args:
            plain_password: The password to verify
            hashed_password: The hashed password to compare against
            
        Returns:
            bool: True if password matches, False otherwise
        """
        pass