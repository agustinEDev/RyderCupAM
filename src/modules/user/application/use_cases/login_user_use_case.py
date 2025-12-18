"""
Login User Use Case

Caso de uso para autenticar un usuario y generar un token JWT.
Session Timeout (v1.8.0): Genera access token (15 min) + refresh token (7 días).
Security Logging (v1.8.0): Registra todos los intentos de login (exitosos y fallidos).
"""


from src.modules.user.application.dto.user_dto import (
    LoginRequestDTO,
    LoginResponseDTO,
    UserResponseDTO,
)
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.shared.infrastructure.logging.security_logger import get_security_logger


class LoginUserUseCase:
    """
    Caso de uso para login de usuario.

    Responsabilidades:
    - Buscar usuario por email
    - Verificar contraseña
    - Generar access token JWT (15 min)
    - Generar refresh token JWT (7 días)
    - Guardar refresh token en BD (hasheado)
    - Devolver tokens y datos de usuario

    Session Timeout (v1.8.0):
    - Access token de corta duración (15 min) para seguridad
    - Refresh token de larga duración (7 días) para UX
    - Refresh token almacenado hasheado en BD (OWASP A02)
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        token_service: ITokenService
    ):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorios (users + refresh_tokens)
            token_service: Servicio para generación de tokens de autenticación
        """
        self._uow = uow
        self._token_service = token_service

    async def execute(self, request: LoginRequestDTO) -> LoginResponseDTO | None:
        """
        Ejecuta el caso de uso de login.

        Args:
            request: DTO con email, password y contexto de seguridad (IP, User-Agent)

        Returns:
            LoginResponseDTO con access token, refresh token y datos de usuario
            None si el usuario no existe o las credenciales son inválidas

        Security Logging (v1.8.0):
            - Registra TODOS los intentos de login (exitosos y fallidos)
            - Severity HIGH para fallos (posible brute force)
            - Severity MEDIUM para éxitos (evento normal)

        Example:
            >>> request = LoginRequestDTO(
            ...     email="user@example.com",
            ...     password="P@ssw0rd123!",
            ...     ip_address="192.168.1.1",
            ...     user_agent="Mozilla/5.0..."
            ... )
            >>> response = await use_case.execute(request)
            >>> if response:
            >>>     print(response.access_token)  # Válido 15 min
            >>>     print(response.refresh_token)  # Válido 7 días
        """
        # Obtener security logger
        security_logger = get_security_logger()

        # Buscar usuario por email
        email = Email(request.email)
        user = await self._uow.users.find_by_email(email)

        # Valores por defecto para security logging si no se proporcionan
        ip_address = request.ip_address or "unknown"
        user_agent = request.user_agent or "unknown"

        if not user:
            # Security Logging: Login fallido (usuario no existe)
            security_logger.log_login_attempt(
                user_id=None,
                email=request.email,
                success=False,
                failure_reason="User not found",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return None

        # Verificar contraseña
        if not user.verify_password(request.password):
            # Security Logging: Login fallido (contraseña incorrecta)
            security_logger.log_login_attempt(
                user_id=str(user.id.value),
                email=request.email,
                success=False,
                failure_reason="Invalid credentials",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return None

        # Registrar evento de login exitoso (Clean Architecture)
        from datetime import datetime
        login_time = datetime.now()
        user.record_login(
            logged_in_at=login_time,
            # ip_address y user_agent se pueden agregar cuando el controlador los pase
            # session_id se podría generar aquí si fuera necesario
        )

        # Generar access token JWT (15 minutos)
        access_token = self._token_service.create_access_token(
            data={"sub": str(user.id.value)}
        )

        # Generar refresh token JWT (7 días)
        refresh_token_jwt = self._token_service.create_refresh_token(
            data={"sub": str(user.id.value)}
        )

        # Crear entidad RefreshToken (hashea el JWT antes de guardar)
        refresh_token_entity = RefreshToken.create(
            user_id=user.id,
            token=refresh_token_jwt,
            expires_in_days=7
        )

        # Persistir usuario + refresh token usando Unit of Work
        async with self._uow:
            await self._uow.users.save(user)
            await self._uow.refresh_tokens.save(refresh_token_entity)
            # Commit automático al salir del contexto

        # Security Logging: Login exitoso
        security_logger.log_login_attempt(
            user_id=str(user.id.value),
            email=request.email,
            success=True,
            failure_reason=None,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Crear respuesta con tokens y datos de usuario
        user_dto = UserResponseDTO.model_validate(user)

        return LoginResponseDTO(
            access_token=access_token,
            refresh_token=refresh_token_jwt,
            token_type="bearer",
            user=user_dto,
            email_verification_required=not user.is_email_verified()
        )
