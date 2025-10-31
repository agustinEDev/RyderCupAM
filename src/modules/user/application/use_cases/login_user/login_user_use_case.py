"""Login User Use Case."""
from src.modules.user.domain.repositories.user_repository import UserRepository
from src.modules.user.domain.services.password_hasher import PasswordHasher
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.errors.user_errors import InvalidCredentialsError
from src.modules.user.application.services.token_service import TokenService
from src.modules.user.application.use_cases.login_user.login_user_dto import (
    LoginUserCommand,
    LoginUserResponse,
    UserData,
)


class LoginUserUseCase:
    """Use case for user authentication.
    
    This orchestrates the login process:
    1. Find user by email
    2. Verify password
    3. Generate access token
    4. Return token and user data
    
    Security note: We use a generic error message to avoid
    leaking information about whether the email exists.
    """
    
    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
    ):
        """Initialize the use case with its dependencies.
        
        Args:
            user_repository: Repository for user persistence
            password_hasher: Service for password verification
            token_service: Service for token generation
        """
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._token_service = token_service
    
    async def execute(self, command: LoginUserCommand) -> LoginUserResponse:
        """Execute the login user use case.
        
        Args:
            command: Command containing login credentials
            
        Returns:
            LoginUserResponse: Access token and user data
            
        Raises:
            InvalidCredentialsError: If credentials are invalid
            ValueError: If email format is invalid
        """
        # Find user by email
        email = Email.create(command.email)
        user = await self._user_repository.find_by_email(email)
        
        if user is None:
            raise InvalidCredentialsError()
        
        # Verify password
        is_valid = await user.verify_password(command.password, self._password_hasher)
        
        if not is_valid:
            raise InvalidCredentialsError()
        
        # Generate access token
        access_token = self._token_service.generate(
            user_id=user.id.to_string(),
            email=str(user.email),
        )
        
        # Return response with token and user data
        return LoginUserResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserData(
                id=user.id.to_string(),
                email=str(user.email),
                first_name=user.first_name,
                last_name=user.last_name,
            ),
        )