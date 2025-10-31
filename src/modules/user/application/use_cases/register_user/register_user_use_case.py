"""Register User Use Case."""
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_repository import UserRepository
from src.modules.user.domain.services.password_hasher import PasswordHasher
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.errors.user_errors import EmailAlreadyExistsError
from src.modules.user.application.use_cases.register_user.register_user_dto import (
    RegisterUserRequestDTO,
    RegisterUserResponseDTO,
)


class RegisterUserUseCase:
    """Use case for registering a new user in the system.
    
    This orchestrates the registration process following business rules:
    1. Validate email is not already registered
    2. Create user with hashed password
    3. Persist user in repository
    4. Return user data (without password)
    """
    
    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
    ):
        """Initialize the use case with its dependencies.
        
        Args:
            user_repository: Repository for user persistence
            password_hasher: Service for hashing passwords
        """
        self._user_repository = user_repository
        self._password_hasher = password_hasher

    async def execute(self, command: RegisterUserRequestDTO) -> RegisterUserResponseDTO:
        """Execute the register user use case.
        
        Args:
            command: Command containing registration data
            
        Returns:
            RegisterUserResponse: Registered user data
            
        Raises:
            EmailAlreadyExistsError: If email is already registered
            ValueError: If any validation fails
        """
        # Check if email already exists
        email = Email.create(command.email)
        if await self._user_repository.exists_by_email(email):
            raise EmailAlreadyExistsError(command.email)
        
        # Create user entity
        user = await User.create(
            email=command.email,
            plain_password=command.password,
            first_name=command.first_name,
            last_name=command.last_name,
            hasher=self._password_hasher,
        )
        
        # Persist user
        saved_user = await self._user_repository.save(user)
        
        # Return response DTO
        return RegisterUserResponseDTO(
            id=saved_user.id.to_string(),
            email=str(saved_user.email),
            first_name=saved_user.first_name,
            last_name=saved_user.last_name,
            created_at=saved_user.created_at,
        )