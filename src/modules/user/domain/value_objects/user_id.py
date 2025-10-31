"""User ID Value Object."""
from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True)
class UserId:
    """User identifier as a Value Object.
    
    Represents a unique identifier for a user using UUID v4.
    Being immutable (frozen), it guarantees identity consistency.
    """
    
    value: UUID
    
    @classmethod
    def generate(cls) -> "UserId":
        """Generate a new unique user ID.
        
        Returns:
            UserId: A new user identifier
        """
        return cls(value=uuid4())
    
    @classmethod
    def from_string(cls, user_id: str) -> "UserId":
        """Create a UserId from a string representation.
        
        Args:
            user_id: String representation of UUID
            
        Returns:
            UserId: User identifier instance
            
        Raises:
            ValueError: If the string is not a valid UUID
        """
        try:
            return cls(value=UUID(user_id))
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid user ID format: {user_id}") from e
    
    def to_string(self) -> str:
        """Convert to string representation.
        
        Returns:
            str: String representation of the UUID
        """
        return str(self.value)
    
    def __str__(self) -> str:
        return self.to_string()
    
    def __repr__(self) -> str:
        return f"UserId({self.value})"