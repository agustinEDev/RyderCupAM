"""
Login User Use Case

Caso de uso para autenticar un usuario y generar un token JWT.
Session Timeout (v1.8.0): Genera access token (15 min) + refresh token (7 días).
Security Logging (v1.8.0): Registra todos los intentos de login (exitosos y fallidos).
Account Lockout (v1.13.0): Bloquea cuenta tras 10 intentos fallidos por 30 minutos.
CSRF Protection (v1.13.0): Genera token CSRF de 256 bits para validación double-submit.
"""

from datetime import UTC, datetime
from typing import NoReturn

from src.config.csrf_config import generate_csrf_token
from src.modules.user.application.dto.device_dto import (
    UNRESOLVED_IP_PLACEHOLDER,
    RegisterDeviceRequestDTO,
    agente_para_el_registro,
)
from src.modules.user.application.dto.user_dto import (
    LoginRequestDTO,
    LoginResponseDTO,
    UserResponseDTO,
)
from src.modules.user.application.ports.aviso_de_nuevo_inicio_port import IAvisoDeNuevoInicio
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.modules.user.application.services.datos_del_acceso import datos_del_acceso
from src.modules.user.application.use_cases.register_device_use_case import (
    RegisterDeviceUseCase,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.exceptions import AccountDeactivatedException, AccountLockedException
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.shared.infrastructure.logging.security_logger import get_security_logger
from src.shared.infrastructure.security.bcrypt_executor import run_bcrypt


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
        aviso_de_nuevo_inicio: IAvisoDeNuevoInicio | None = None,
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
        # El correo de «nuevo inicio de sesión» (BE #737); sin él, no se avisa
        self._aviso_de_nuevo_inicio = aviso_de_nuevo_inicio

    @staticmethod
    def _apunta_que_no_existe(request: LoginRequestDTO, ip_address: str, user_agent: str) -> None:
        """Security Logging: login fallido porque el usuario no existe."""
        get_security_logger().log_login_attempt(
            user_id=None,
            email=request.email,
            success=False,
            failure_reason="User not found",
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def _rechaza_por_bloqueo(
        user: User, request: LoginRequestDTO, ip_address: str, user_agent: str
    ) -> NoReturn:
        """Security Logging del intento sobre una cuenta bloqueada, y la excepción."""
        locked_until = user.locked_until
        get_security_logger().log_login_attempt(
            user_id=str(user.id.value),
            email=request.email,
            success=False,
            failure_reason=f"Account locked until {locked_until.isoformat()}",
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise AccountLockedException(
            locked_until=locked_until,
            message=f"Account is locked due to too many failed login attempts. Try again after {locked_until.isoformat()}",
        )

    async def _apunta_el_fallo(
        self, user: User, request: LoginRequestDTO, ip_address: str, user_agent: str
    ) -> None:
        """
        Account Lockout (v1.13.0): registra el intento fallido sobre el usuario
        RELEÍDO con la fila bloqueada (BE #282). Sin el bloqueo, dos intentos a
        la vez leían N y escribían N+1, y el bloqueo de los 10 no saltaba nunca.
        El bcrypt ya pasó: la transacción es corta.

        Raises:
            AccountLockedException: si este intento bloquea la cuenta
        """
        async with self._uow:
            bloqueado = await self._uow.users.find_by_id_for_update(user.id)
            # Sobre una que otro acaba de bloquear no se cuenta: alargaría el
            # bloqueo y repetiría su evento por cada intento en vuelo (code-review)
            if bloqueado is not None and not bloqueado.is_locked():
                bloqueado.record_failed_login()
                await self._uow.users.save(bloqueado)
            # Commit automático al salir del contexto

        if bloqueado is None:
            # Se borró entre la lectura y el bloqueo: como un email que no existe
            self._apunta_que_no_existe(request, ip_address, user_agent)
            return

        # Si la cuenta quedó bloqueada en este intento, lanzar excepción
        if bloqueado.is_locked():
            self._rechaza_por_bloqueo(bloqueado, request, ip_address, user_agent)

        # Security Logging: Login fallido (contraseña incorrecta)
        get_security_logger().log_login_attempt(
            user_id=str(bloqueado.id.value),
            email=request.email,
            success=False,
            failure_reason="Invalid credentials",
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def _releido_para_entrar(
        self, user: User, request: LoginRequestDTO, ip_address: str, user_agent: str
    ) -> User | None:
        """
        Con la contraseña buena, el usuario releído con la fila bloqueada antes de
        darla por buena (BE #282, revisor). En una ráfaga, todas las peticiones
        pasaban el `is_locked()` sobre la lectura sin bloqueo: la buena entraba
        aunque otro intento acabara de bloquear la cuenta, y además deshacía el
        bloqueo al poner el contador a cero.

        Returns:
            El usuario releído, o None si se borró entre medias

        Raises:
            AccountLockedException: si otro intento la acaba de bloquear
        """
        async with self._uow:
            releido = await self._uow.users.find_by_id_for_update(user.id)
            # El cero, DENTRO de la transacción bloqueada: guardado más tarde,
            # pisaba los fallos que llegaran entre medias (code-review)
            if releido is not None and not releido.is_locked():
                releido.reset_failed_attempts()
                await self._uow.users.save(releido)
        if releido is None:
            self._apunta_que_no_existe(request, ip_address, user_agent)
            return None
        if releido.is_locked():
            self._rechaza_por_bloqueo(releido, request, ip_address, user_agent)
        return releido

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
            # El mismo bcrypt que una contraseña mala: sin él, responder antes
            # delataba qué emails están registrados (BE #281, OWASP A07)
            await run_bcrypt(Password.verifica_contra_el_relleno, request.password)
            # Security Logging: Login fallido (usuario no existe)
            self._apunta_que_no_existe(request, ip_address, user_agent)
            return None

        # Account Lockout (v1.13.0): Verificar si la cuenta está bloqueada
        if user.is_locked():
            # Security Logging y excepción con información del bloqueo
            self._rechaza_por_bloqueo(user, request, ip_address, user_agent)

        # Verificar contraseña
        if not await run_bcrypt(user.verify_password, request.password):
            await self._apunta_el_fallo(user, request, ip_address, user_agent)
            return None

        # La buena, pero RELEÍDA con la fila bloqueada (BE #282, revisor)
        releido = await self._releido_para_entrar(user, request, ip_address, user_agent)
        if releido is None:
            return None
        user = releido

        # Account Lockout (v1.13.0): los intentos fallidos ya se pusieron a cero
        # en `_releido_para_entrar`, con la fila bloqueada

        # Admin Panel (v2.4.0): Verificar si la cuenta fue desactivada por un admin.
        # Se comprueba DESPUES de validar la contraseña para no filtrar el estado
        # de la cuenta (activa/desactivada) a quien no conoce las credenciales.
        if not user.is_active:
            security_logger.log_login_attempt(
                user_id=str(user.id.value),
                email=request.email,
                success=False,
                failure_reason="Account deactivated by admin",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AccountDeactivatedException()

        # Registrar evento de login exitoso (Clean Architecture)
        login_time = datetime.now(UTC)
        user.record_login(
            logged_in_at=login_time,
            # ip_address y user_agent se pueden agregar cuando el controlador los pase
            # session_id se podría generar aquí si fuera necesario
        )

        # Device Fingerprinting (v2.0.4): Registrar/actualizar dispositivo PRIMERO
        # Cookie-based identification: device_id_from_cookie tiene prioridad
        # Necesitamos el device_id para asociarlo con el refresh token
        device_id = None
        should_set_device_cookie = False
        device_id_str = None
        es_nuevo = False
        # Siempre con dispositivo, también sin User-Agent: una sesión sin él no salía en
        # la lista, no avisaba y no se podía revocar (auditoría OWASP, A07)
        device_request = RegisterDeviceRequestDTO(
            user_id=str(user.id.value),
            user_agent=agente_para_el_registro(request.user_agent),
            ip_address=request.ip_address or UNRESOLVED_IP_PLACEHOLDER,
            device_id_from_cookie=request.device_id_from_cookie,
            installed_app=request.installed_app,  # BE #737
            country_code=request.country_code,
        )
        # Registrar dispositivo (crea nuevo o actualiza last_used_at + ip_address)
        device_response = await self._register_device_use_case.execute(device_request)
        # Obtener device_id para asociar con refresh token
        device_id = UserDeviceId.from_string(device_response.device_id)
        device_id_str = device_response.device_id
        should_set_device_cookie = device_response.set_device_cookie
        es_nuevo = device_response.is_new_device

        # Los tokens, después del dispositivo: el de acceso lleva su id (`did`), y así
        # revocarlo se comprueba por id y no por una huella que cambia (BE #737)
        access_token = self._token_service.create_access_token(
            data=datos_del_acceso(str(user.id.value), device_id_str)
        )
        refresh_token_jwt = self._token_service.create_refresh_token(
            data={"sub": str(user.id.value)}
        )

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

        # Si entra desde un dispositivo nuevo, se le avisa por correo (BE #737). No
        # lanza: un fallo del correo no tumba el login
        if self._aviso_de_nuevo_inicio is not None and user.email is not None:
            # Nunca a un correo sin confirmar: solo le llega el de confirmación
            await self._aviso_de_nuevo_inicio.avisa(
                user.id,
                user.email.value,
                user.first_name,
                device_id_str,
                es_nuevo,
                verificado=user.is_email_verified(),
            )

        # Generar token CSRF (256 bits, 15 minutos de duración)
        csrf_token = generate_csrf_token(str(user.id.value))

        # El hándicap ya no se refresca aquí: el login esperaba a la RFEG antes de
        # contestar. Lo pide el frontend después de entrar (RyderCupAM#340).

        # Crear respuesta con tokens y datos de usuario
        user_dto = UserResponseDTO.model_validate(user)

        return LoginResponseDTO(
            access_token=access_token,
            refresh_token=refresh_token_jwt,
            csrf_token=csrf_token,
            token_type="bearer",  # nosec B106 - Not a password, it's OAuth2 token type
            user=user_dto,
            email_verification_required=not user.is_email_verified(),
            # Device Fingerprinting (v2.0.4): Cookie-based identification
            device_id=device_id_str,
            should_set_device_cookie=should_set_device_cookie,
        )
