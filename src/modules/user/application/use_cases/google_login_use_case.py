"""
Google Login Use Case - Application Layer

Caso de uso para login/registro con Google OAuth.
Soporta tres flujos:
1. Usuario OAuth existente → login directo
2. Usuario email existente → auto-link + login
3. Usuario nuevo → auto-register + login
"""

import logging
from datetime import datetime

from src.config.csrf_config import generate_csrf_token
from src.modules.user.application.dto.device_dto import (
    UNRESOLVED_IP_PLACEHOLDER,
    AvisoDeNuevoInicioRequestDTO,
    RegisterDeviceRequestDTO,
    agente_para_el_registro,
)
from src.modules.user.application.dto.oauth_dto import (
    GoogleLoginRequestDTO,
    GoogleLoginResponseDTO,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.application.ports.aviso_de_nuevo_inicio_port import IAvisoDeNuevoInicio
from src.modules.user.application.ports.google_oauth_service_interface import (
    GoogleUserInfo,
    IGoogleOAuthService,
)
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.modules.user.application.services.datos_del_acceso import datos_del_acceso
from src.modules.user.application.use_cases.register_device_use_case import (
    RegisterDeviceUseCase,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.exceptions import AccountDeactivatedException
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.shared.infrastructure.logging.security_logger import get_security_logger

logger = logging.getLogger(__name__)


class GoogleEmailNotVerifiedError(ValueError):
    """Google no ha verificado el correo de esa cuenta: ni alta ni vínculo.

    Sin esta regla, cualquiera con una cuenta de Google con tu dirección, sin
    verificar, entraba en la tuya (el vínculo automático por correo) o te la dejaba
    ocupada (el alta). La ruta responde 400 con GOOGLE_EMAIL_NOT_VERIFIED.
    """


class GoogleLoginUseCase:
    """
    Caso de uso para login/registro con Google OAuth.

    Flujo:
    1. Intercambiar authorization code por user info de Google
    2. Buscar OAuth account existente → login directo
    3. Buscar usuario por email → auto-link + login
    4. Crear usuario nuevo → auto-register + login
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        token_service: ITokenService,
        google_oauth_service: IGoogleOAuthService,
        register_device_use_case: RegisterDeviceUseCase,
        aviso_de_nuevo_inicio: IAvisoDeNuevoInicio,
    ):
        # El correo de «nuevo inicio de sesión» (BE #737)
        self._aviso_de_nuevo_inicio = aviso_de_nuevo_inicio
        self._uow = uow
        self._token_service = token_service
        self._google_oauth_service = google_oauth_service
        self._register_device_use_case = register_device_use_case

    async def _resolve_user(self, google_info: GoogleUserInfo) -> tuple[User, bool, bool]:
        """
        Resuelve el usuario para el login de Google.
        Todas las lecturas y escrituras se ejecutan dentro de una sola transacción UoW.

        Returns:
            Tuple of (user, is_new_user, linked): linked, si se vinculó por el correo
        """
        async with self._uow:
            # Buscar OAuth account existente
            oauth_account = await self._uow.oauth_accounts.find_by_provider_and_provider_user_id(
                OAuthProvider.GOOGLE, google_info.google_user_id
            )

            if oauth_account:
                user = await self._uow.users.find_by_id(oauth_account.user_id)
                if not user:
                    raise ValueError("User associated with OAuth account not found")
                return user, False, False

            # Sin cuenta vinculada: un alta o un vínculo por correo. Solo con el correo
            # verificado por Google: si no, la dirección no es necesariamente suya
            if not google_info.email_verified:
                raise GoogleEmailNotVerifiedError("Google email is not verified")

            # Buscar usuario por email
            email = Email(google_info.email)
            user = await self._uow.users.find_by_email(email)

            if user:
                # Desactivada: sin vincular Google ni verificar el correo. Un login
                # rechazado no cambia la cuenta (/code-review); execute da el 403
                if not user.is_active:
                    return user, False, False
                return await self._auto_link_existing_user(user, google_info), False, True

            return await self._auto_register_new_user(google_info), True, False

    async def _auto_link_existing_user(self, user: User, google_info: GoogleUserInfo) -> User:
        """
        Auto-link Google account to existing user found by email.
        Ejecuta dentro del contexto UoW del caller (sin abrir transacción propia).
        """
        new_oauth = UserOAuthAccount.create(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id=google_info.google_user_id,
            provider_email=google_info.email,
        )
        await self._uow.oauth_accounts.save(new_oauth)

        # Google ha verificado el correo (si no, no se llega aquí)
        if not user.email_verified:
            user.verify_email_from_oauth()

        await self._uow.users.save(user)
        return user

    async def _auto_register_new_user(self, google_info: GoogleUserInfo) -> User:
        """
        Auto-register a new user from Google profile.
        Ejecuta dentro del contexto UoW del caller (sin abrir transacción propia).
        """
        user = User.create_from_oauth(
            first_name=google_info.first_name,
            last_name=google_info.last_name,
            email_str=google_info.email,
            email_verified=google_info.email_verified,
        )
        new_oauth = UserOAuthAccount.create(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id=google_info.google_user_id,
            provider_email=google_info.email,
        )
        await self._uow.users.save(user)
        await self._uow.oauth_accounts.save(new_oauth)
        return user

    async def _register_device(self, request: GoogleLoginRequestDTO, user_id_str: str):
        """Register device and return (device_id, device_id_str, is_new)."""
        # Siempre con dispositivo, también sin User-Agent (auditoría OWASP, A07)
        device_request = RegisterDeviceRequestDTO(
            user_id=user_id_str,
            user_agent=agente_para_el_registro(request.user_agent),
            ip_address=request.ip_address or UNRESOLVED_IP_PLACEHOLDER,
            device_id_from_cookie=request.device_id_from_cookie,
            installed_app=request.installed_app,
            country_code=request.country_code,
        )
        device_response = await self._register_device_use_case.execute(device_request)
        return (
            UserDeviceId.from_string(device_response.device_id),
            device_response.device_id,
            # Sin su cookie (nuevo, o solo por la huella) avisa (BE #737)
            device_response.is_new_device or not device_response.recognized_by_cookie,
        )

    async def execute(self, request: GoogleLoginRequestDTO) -> GoogleLoginResponseDTO:
        """
        Ejecuta el flujo de login/registro con Google.

        Args:
            request: DTO con authorization_code y contexto HTTP

        Returns:
            GoogleLoginResponseDTO con tokens, usuario e is_new_user flag

        Raises:
            ValueError: Si el authorization code es inválido
        """
        security_logger = get_security_logger()
        ip_address = request.ip_address or "unknown"
        user_agent = request.user_agent or "unknown"

        # 1. Intercambiar code por info de Google
        google_info = await self._google_oauth_service.exchange_code_for_user_info(
            request.authorization_code
        )

        # 2. Resolve user (existing OAuth, auto-link, or auto-register) — atomic
        user, is_new_user, vinculada = await self._resolve_user(google_info)
        if vinculada:
            # Que quede rastro, ya guardado y con la red: un Google vinculado solo, por
            # el correo, da acceso a la cuenta. El log nunca cambia la respuesta
            try:
                security_logger.log_google_account_linked(
                    user_id=str(user.id.value),
                    automatic=True,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            except Exception as error:
                logger.error("Google link audit event failed: %s", type(error).__name__)

        # Una cuenta desactivada no entra (BE #744, auditoría OWASP): ni sesión, ni
        # dispositivo, ni correo de «nuevo inicio», como con la contraseña
        if not user.is_active:
            security_logger.log_login_attempt(
                user_id=str(user.id.value),
                email=google_info.email,
                success=False,
                failure_reason="Account deactivated by admin",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AccountDeactivatedException()

        # 3. Sin mirar el bloqueo por fallos de contraseña (BE #732): Google ya
        # demuestra que es él, y una cuenta solo de Google no tiene contraseña buena
        # con la que defenderse. Tampoco pone el respaldo a cero: suma todas las
        # redes y se acaba con su hora

        # 4. Login flow
        user.record_login(
            logged_in_at=datetime.now(),
            ip_address=ip_address,
            user_agent=user_agent,
            login_method="google",
        )

        device_id, device_id_str, es_nuevo = await self._register_device(
            request, str(user.id.value)
        )

        # Después del dispositivo: el token de acceso lleva su id (BE #737)
        access_token = self._token_service.create_access_token(
            data=datos_del_acceso(str(user.id.value), device_id_str)
        )
        refresh_token_jwt = self._token_service.create_refresh_token(
            data={"sub": str(user.id.value)}
        )

        refresh_token_entity = RefreshToken.create(
            user_id=user.id, token=refresh_token_jwt, device_id=device_id, expires_in_days=7
        )

        async with self._uow:
            await self._uow.users.save(user)
            await self._uow.refresh_tokens.save(refresh_token_entity)

        # Si entra desde un dispositivo nuevo, se le avisa por correo (BE #737)
        # El alta con Google no avisa: es crear la cuenta
        # Al correo de la CUENTA, no al de Google: si la cuenta se vinculó con
        # otra dirección, o lo comprometido es la cuenta de Google, el aviso tiene
        # que llegar a su dueño (auditoría OWASP, 5 nov 2026)
        await self._aviso_de_nuevo_inicio.avisa(
            AvisoDeNuevoInicioRequestDTO(
                user_id=str(user.id.value),
                email=user.email.value if user.email else google_info.email,
                nombre=user.first_name,
                device_id=device_id_str,
                desconocido=es_nuevo,
                verificado=user.is_email_verified(),
                es_alta=is_new_user,
            )
        )

        security_logger.log_login_attempt(
            user_id=str(user.id.value),
            email=google_info.email,
            success=True,
            failure_reason=None,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return GoogleLoginResponseDTO(
            access_token=access_token,
            refresh_token=refresh_token_jwt,
            csrf_token=generate_csrf_token(str(user.id.value)),
            token_type="bearer",  # nosec B106 - not a password, it's an OAuth token type
            user=UserResponseDTO.model_validate(user),
            is_new_user=is_new_user,
            device_id=device_id_str,
        )
