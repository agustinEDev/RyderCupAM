"""User Repository Interface."""
from abc import ABC, abstractmethod
from typing import Optional

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.domain.value_objects.email import Email


class UserRepository(ABC):
    """Abstract repository interface for User aggregate.
    
    This defines the contract for persistence operations on users.
    The actual implementation will be in the infrastructure layer.
    """
    
    @abstractmethod
    async def save(self, user: User) -> User:
        """Persist a new user.
        
        Args:
            user: User entity to persist
            
        Returns:
            User: The persisted user entity
            
        Raises:
            EmailAlreadyExistsError: If email already exists
        """
        pass
    
    @abstractmethod
    async def find_by_id(self, user_id: UserId) -> Optional[User]:
        """Find a user by their ID.
        
        Args:
            user_id: User identifier
            
        Returns:
            Optional[User]: User entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def find_by_email(self, email: Email) -> Optional[User]:
        """Find a user by their email address.
        
        Args:
            email: Email to search for
            
        Returns:
            Optional[User]: User entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def exists_by_email(self, email: Email) -> bool:
        """Check if a user exists with the given email.
        
        Args:
            email: Email to check
            
        Returns:
            bool: True if user exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def update(self, user: User) -> User:
        """Update an existing user.
        
        Args:
            user: User entity with updated data
            
        Returns:
            User: Updated user entity
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        pass
    
    @abstractmethod
    async def delete(self, user_id: UserId) -> None:
        """Delete a user.
        
        Args:
            user_id: ID of user to delete
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        pass