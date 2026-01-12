"""
Login User Use Case

Caso de uso para autenticar un usuario y generar un token JWT.
Session Timeout (v1.8.0): Genera access token (15 min) + refresh token (7 días).
Security Logging (v1.8.0): Registra todos los intentos de login (exitosos y fallidos).
Account Lockout (v1.13.0): Bloquea cuenta tras 10 intentos fallidos por 30 minutos.
CSRF Protection (v1.13.0): Genera token CSRF de 256 bits para validación double-submit.
"""

from datetime import datetime

from src.config.csrf_config import generate_csrf_token
from src.modules.user.application.dto.device_dto import RegisterDeviceRequestDTO
from src.modules.user.application.dto.user_dto import (
    LoginRequestDTO,
    LoginResponseDTO,
    UserResponseDTO,
)
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.modules.user.application.use_cases.register_device_use_case import (
    RegisterDeviceUseCase,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.exceptions import AccountLockedException
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
        token_service: ITokenService,
        register_device_use_case: RegisterDeviceUseCase,
    ):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorios (users + refresh_tokens + user_devices)
            token_service: Servicio para generación de tokens de autenticación
            register_device_use_case: Caso de uso para registrar/actualizar dispositivos (v1.13.0)
        """
        self._uow = uow
        self._token_service = token_service
        self._register_device_use_case = register_device_use_case

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

        # Account Lockout (v1.13.0): Verificar si la cuenta está bloqueada
        if user.is_locked():
            # Security Logging: Intento de login en cuenta bloqueada
            security_logger.log_login_attempt(
                user_id=str(user.id.value),
                email=request.email,
                success=False,
                failure_reason=f"Account locked until {user.locked_until.isoformat()}",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            # Lanzar excepción con información del bloqueo
            raise AccountLockedException(
                locked_until=user.locked_until,
                message=f"Account is locked due to too many failed login attempts. Try again after {user.locked_until.isoformat()}",
            )

        # Verificar contraseña
        if not user.verify_password(request.password):
            # Account Lockout (v1.13.0): Registrar intento fallido
            user.record_failed_login()

            # Persistir cambios (incremento de failed_login_attempts)
            async with self._uow:
                await self._uow.users.save(user)
                # Commit automático al salir del contexto

            # Si la cuenta quedó bloqueada en este intento, lanzar excepción
            if user.is_locked():
                security_logger.log_login_attempt(
                    user_id=str(user.id.value),
                    email=request.email,
                    success=False,
                    failure_reason=f"Account locked until {user.locked_until.isoformat()}",
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                raise AccountLockedException(
                    locked_until=user.locked_until,
                    message=f"Account is locked due to too many failed login attempts. Try again after {user.locked_until.isoformat()}",
                )

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

        # Account Lockout (v1.13.0): Resetear intentos fallidos tras login exitoso
        user.reset_failed_attempts()

        # Registrar evento de login exitoso (Clean Architecture)
        login_time = datetime.now()
        user.record_login(
            logged_in_at=login_time,
            # ip_address y user_agent se pueden agregar cuando el controlador los pase
            # session_id se podría generar aquí si fuera necesario
        )

        # Generar access token JWT (15 minutos)
        access_token = self._token_service.create_access_token(data={"sub": str(user.id.value)})

        # Generar refresh token JWT (7 días)
        refresh_token_jwt = self._token_service.create_refresh_token(
            data={"sub": str(user.id.value)}
        )

        # Device Fingerprinting (v1.13.0): Registrar/actualizar dispositivo PRIMERO
        # Necesitamos el device_id para asociarlo con el refresh token
        device_id = None
        if request.user_agent and request.ip_address:
            device_request = RegisterDeviceRequestDTO(
                user_id=str(user.id.value),
                user_agent=request.user_agent,
                ip_address=request.ip_address,
            )
            # Registrar dispositivo (crea nuevo o actualiza last_used_at)
            device_response = await self._register_device_use_case.execute(device_request)
            # Obtener device_id para asociar con refresh token
            from src.modules.user.domain.value_objects.user_device_id import UserDeviceId

            device_id = UserDeviceId.from_string(device_response.device_id)

        # Crear entidad RefreshToken (hashea el JWT antes de guardar)
        # IMPORTANTE: Asociar con device_id para permitir revocación correcta
        refresh_token_entity = RefreshToken.create(
            user_id=user.id, token=refresh_token_jwt, device_id=device_id, expires_in_days=7
        )

        # Persistir usuario + refresh token usando Unit of Work
        async with self._uow:
            await self._uow.users.save(user)
            await self._uow.refresh_tokens.save(refresh_token_entity)
            # Commit automático al salir del contexto
            # Nota: Device ya fue persistido en su propio UoW dentro de RegisterDeviceUseCase

        # Security Logging: Login exitoso
        security_logger.log_login_attempt(
            user_id=str(user.id.value),
            email=request.email,
            success=True,
            failure_reason=None,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Generar token CSRF (256 bits, 15 minutos de duración)
        csrf_token = generate_csrf_token()

        # Crear respuesta con tokens y datos de usuario
        user_dto = UserResponseDTO.model_validate(user)

        return LoginResponseDTO(
            access_token=access_token,
            refresh_token=refresh_token_jwt,
            csrf_token=csrf_token,
            token_type="bearer",  # nosec B106 - Not a password, it's OAuth2 token type
            user=user_dto,
            email_verification_required=not user.is_email_verified(),
        )
