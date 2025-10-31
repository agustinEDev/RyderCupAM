"""User Domain Errors."""


class UserDomainError(Exception):
    """Base exception for user domain errors."""
    pass


class EmailAlreadyExistsError(UserDomainError):
    """Raised when trying to register with an email that already exists."""
    
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"User with email '{email}' already exists")


class UserNotFoundError(UserDomainError):
    """Raised when a user is not found."""
    
    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"User not found: {identifier}")


class InvalidCredentialsError(UserDomainError):
    """Raised when login credentials are invalid.
    
    This error is generic to avoid leaking information about
    whether the user exists or the password is wrong.
    """
    
    def __init__(self):
        super().__init__("Invalid email or password")