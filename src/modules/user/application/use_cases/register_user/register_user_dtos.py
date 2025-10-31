"""DTOs for Register User use case."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RegisterUserRequestDTO:
    """Command to register a new user.
    
    This is the input DTO for the register user use case.
    """
    email: str
    password: str
    first_name: str
    last_name: str


@dataclass(frozen=True)
class RegisterUserResponseDTO:
    """Response from registering a new user.
    
    This is the output DTO for the register user use case.
    """
    id: str
    email: str
    first_name: str
    last_name: str
    created_at: datetime