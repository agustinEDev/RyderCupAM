"""Token Service Interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TokenPayload:
    """Payload data extracted from a token."""
    user_id: str
    email: str


class TokenService(ABC):
    """Abstract interface for token operations.
    
    This is an application service interface for JWT token management.
    The actual implementation will be in the infrastructure layer.
    """
    
    @abstractmethod
    def generate(self, user_id: str, email: str) -> str:
        """Generate a new access token.
        
        Args:
            user_id: User identifier
            email: User email
            
        Returns:
            str: Generated JWT token
        """
        pass
    
    @abstractmethod
    def verify(self, token: str) -> TokenPayload:
        """Verify and decode a token.
        
        Args:
            token: JWT token to verify
            
        Returns:
            TokenPayload: Decoded token payload
            
        Raises:
            InvalidTokenError: If token is invalid or expired
        """
        pass
    
    @abstractmethod
    def decode(self, token: str) -> Optional[TokenPayload]:
        """Decode a token without verification (for inspection).
        
        Args:
            token: JWT token to decode
            
        Returns:
            Optional[TokenPayload]: Decoded payload or None if invalid
        """
        pass