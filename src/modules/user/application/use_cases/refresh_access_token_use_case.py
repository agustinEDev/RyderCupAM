"""
Refresh Access Token Use Case

Caso de uso para renovar el access token usando un refresh token válido.
Implementa el patrón Session Timeout (OWASP A01/A02 - v1.8.0).
Security Logging (v1.8.0): Registra uso de refresh tokens.
CSRF Protection (v1.13.0): Genera nuevo token CSRF al renovar access token.
Dispositivos (BE #737, #738): usa y actualiza el dispositivo de su refresh token.
"""

from enum import StrEnum

from src.config.csrf_config import generate_csrf_token
from src.modules.user.application.dto.device_dto import (
    UNRESOLVED_IP_PLACEHOLDER,
)
from src.modules.user.application.dto.user_dto import (
    RefreshAccessTokenRequestDTO,
    RefreshAccessTokenResponseDTO,
    UserResponseDTO,
)
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.modules.user.application.services.datos_del_acceso import datos_del_acceso
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import InvalidUserIdError, UserId
from src.shared.infrastructure.logging.security_logger import get_security_logger


class RefreshRejection(StrEnum):
    """
    Por qué no se renueva la sesión: el motivo exacto, para el log de seguridad.

    Al cliente solo le llega su código público (`codigo_publico`, BE #733).
    """

    # El final normal
    REFRESH_TOKEN_MISSING = "REFRESH_TOKEN_MISSING"  # nosec B105 - an error code
    REFRESH_TOKEN_EXPIRED = "REFRESH_TOKEN_EXPIRED"  # nosec B105 - an error code
    SESSION_IDLE = "SESSION_IDLE"
    # Lo raro
    REFRESH_TOKEN_INVALID = "REFRESH_TOKEN_INVALID"  # nosec B105 - an error code
    REFRESH_TOKEN_NOT_FOUND = "REFRESH_TOKEN_NOT_FOUND"  # nosec B105 - an error code
    REFRESH_TOKEN_REVOKED = "REFRESH_TOKEN_REVOKED"  # nosec B105 - an error code
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_INACTIVE = "USER_INACTIVE"  # desactivada por un administrador (BE #744)


_FINAL_NORMAL = frozenset(
    {
        RefreshRejection.REFRESH_TOKEN_MISSING,
        RefreshRejection.REFRESH_TOKEN_EXPIRED,
        RefreshRejection.SESSION_IDLE,
    }
)
SESSION_ENDED = "SESSION_ENDED"
SESSION_REJECTED = "SESSION_REJECTED"


def codigo_publico(motivo: RefreshRejection) -> str:
    """
    El código que ve el cliente (BE #733): SESSION_ENDED o SESSION_REJECTED.

    El motivo exacto le decía a quien tuviera una cookie de refresco robada si la
    cuenta se borró, si cambió la contraseña o si cerró sesión (OWASP A01/A04). Al
    front le basta separar el final normal de un rechazo; el motivo se queda en el
    log de seguridad.
    """
    return SESSION_ENDED if motivo in _FINAL_NORMAL else SESSION_REJECTED


class RefreshRejectedError(Exception):
    """La sesión no se renueva, con su motivo. La ruta responde 401."""

    def __init__(self, motivo: RefreshRejection, user_id: str | None = None):
        super().__init__(motivo.value)
        self.motivo = motivo
        # Para el log de seguridad (BE #733), nunca para el cliente
        self.user_id = user_id


class RefreshAccessTokenUseCase:
    """
    Caso de uso para renovar el access token usando un refresh token.

    Flujo:
    1. Validar que el refresh token sea válido (vía ITokenService)
    2. Verificar que el refresh token NO esté revocado en BD
    3. Verificar que el usuario sigue existiendo y activo
    4. Generar nuevo access token (15 min)
    5. Retornar nuevo access token + datos de usuario

    Responsabilidades:
    - Validar refresh token (JWT + base de datos)
    - Verificar que el usuario existe
    - Generar nuevo access token
    - Mantener seguridad: NO renovar el refresh token automáticamente

    OWASP Coverage:
    - A01: Broken Access Control - Tokens de corta duración
    - A02: Cryptographic Failures - Refresh tokens en BD con hash
    - A07: Identification and Authentication Failures - Renovación segura
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        token_service: ITokenService,
    ):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorios (users, refresh_tokens, user_devices)
            token_service: Servicio para validación y generación de tokens JWT
        """
        self._uow = uow
        self._token_service = token_service

    async def execute(
        self, request: RefreshAccessTokenRequestDTO, refresh_token_jwt: str
    ) -> RefreshAccessTokenResponseDTO:
        """
        Ejecuta el caso de uso de renovación de access token.

        Args:
            request: DTO de entrada con contexto de seguridad (IP, User-Agent)
            refresh_token_jwt: Refresh token JWT obtenido de la cookie httpOnly

        Returns:
            RefreshAccessTokenResponseDTO con nuevo access token si el refresh token es válido

        Raises:
            RefreshRejectedError: con el motivo, si la sesión no se renueva (FE #1042)

        Security Logging (v1.8.0):
            - Registra uso exitoso de refresh token
            - Severity LOW (acción normal de renovación)

        Example:
            >>> request = RefreshAccessTokenRequestDTO(
            ...     ip_address="192.168.1.1",
            ...     user_agent="Mozilla/5.0..."
            ... )
            >>> response = await use_case.execute(request, "eyJ...")  # o RefreshRejectedError
            >>> print(response.access_token)  # Nuevo token válido por 15 min
        """
        # 1. Verificar que el refresh token JWT sea válido (firma + expiración)
        payload = self._token_service.verify_refresh_token(refresh_token_jwt)

        if not payload:
            # Caducado con la firma buena es el final normal; si no, inválido
            if self._token_service.refresh_token_expired(refresh_token_jwt):
                raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_EXPIRED)
            raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_INVALID)

        # 2. Extraer user_id del payload
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_INVALID)

        try:
            user_id = UserId(user_id_str)
        except (ValueError, TypeError, InvalidUserIdError) as error:
            raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_INVALID) from error

        # 3. Verificar que el refresh token NO esté revocado en base de datos
        # Nota: find_by_token_hash espera el JWT token original, NO el hash
        # El repositorio se encarga de hashear internamente
        try:
            return await self._renueva(request, refresh_token_jwt, user_id)
        except RefreshRejectedError as rechazo:
            # Con el usuario del token, para el log de seguridad (revisor de la PR)
            rechazo.user_id = rechazo.user_id or user_id_str
            raise

    async def _renueva(
        self,
        request: RefreshAccessTokenRequestDTO,
        refresh_token_jwt: str,
        user_id: UserId,
    ) -> RefreshAccessTokenResponseDTO:
        """Del token en la BD en adelante: la cuenta, el token, el dispositivo y el acceso."""
        security_logger = get_security_logger()
        user_id_str = str(user_id.value)
        ip_address = request.ip_address or "unknown"
        user_agent = request.user_agent or "unknown"
        refresh_token_entity = await self._uow.refresh_tokens.find_by_token_hash(refresh_token_jwt)
        if not refresh_token_entity:
            # Refresh token no existe en BD (nunca fue creado o ya fue eliminado)
            raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_NOT_FOUND)

        # 4. La cuenta, antes que el token: una desactivada tiene sus tokens revocados,
        # y el motivo del log tiene que ser ese y no «revocado» (revisor de la PR)
        user = await self._uow.users.find_by_id(user_id)
        if not user:
            # Usuario fue eliminado
            raise RefreshRejectedError(RefreshRejection.USER_NOT_FOUND)
        if not user.is_active:
            # Desactivada (BE #744): este token, revocado si se coló, para que no
            # vuelva a valer al reactivarla (auditoría OWASP)
            if not refresh_token_entity.revoked:
                async with self._uow:
                    refresh_token_entity.revoke()
                    await self._uow.refresh_tokens.save(refresh_token_entity)
            raise RefreshRejectedError(RefreshRejection.USER_INACTIVE)

        await self._rechaza_si_no_vale(refresh_token_entity)

        # 5. Toda sesión tiene dispositivo desde BE #737. Un token sin él es de antes
        # y ya no queda ninguno vivo (BE #738): no se ata a ninguno, se rechaza
        dispositivo = await self._dispositivo_del_token(refresh_token_entity)
        if dispositivo is None:
            raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_INVALID)
        if not dispositivo.is_active:
            # Un token que se coló sin revocar (una carrera con la revocación): no da
            # acceso a un dispositivo revocado; se revoca (/code-review)
            async with self._uow:
                refresh_token_entity.revoke()
                await self._uow.refresh_tokens.save(refresh_token_entity)
            # Con su motivo: en el log se distingue de reusar un token ya revocado
            security_logger.log_refresh_token_revoked(
                user_id=user_id_str,
                ip_address=ip_address,
                user_agent=user_agent,
                tokens_revoked_count=1,
                reason="device_revoked",
            )
            raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_REVOKED)
        # La sesión de este dispositivo caduca tras 24 h sin usarse (BE #376, OWASP
        # A07). Se revoca: el token no vuelve a servir aunque llegue de otra forma
        if dispositivo.is_idle():
            async with self._uow:
                refresh_token_entity.revoke()
                await self._uow.refresh_tokens.save(refresh_token_entity)
            # Que quede constancia: «la app me echó» tiene que poder explicarse
            security_logger.log_refresh_token_revoked(
                user_id=user_id_str,
                ip_address=ip_address,
                user_agent=user_agent,
                tokens_revoked_count=1,
                reason="idle",
            )
            raise RefreshRejectedError(RefreshRejection.SESSION_IDLE)
        # Refrescar es usar ESTE dispositivo, el del token (ver el método)
        device_id = await self._usa_el_dispositivo(request, dispositivo)

        # 6. Generar nuevo access token (15 minutos)
        # Con el id de su dispositivo: revocarlo se comprueba por id (BE #737)
        new_access_token = self._token_service.create_access_token(
            data=datos_del_acceso(str(user.id.value), device_id)
        )

        # 7. Generar nuevo token CSRF (256 bits, 15 minutos de duración)
        csrf_token = generate_csrf_token(str(user.id.value))

        # 8. Security Logging: Uso exitoso de refresh token
        security_logger.log_refresh_token_used(
            user_id=str(user.id.value),
            ip_address=ip_address,
            user_agent=user_agent,
            refresh_token_id=str(refresh_token_entity.id.value),
            new_access_token_created=True,
        )

        # 9. Preparar respuesta
        user_dto = UserResponseDTO.model_validate(user)

        return RefreshAccessTokenResponseDTO(
            access_token=new_access_token,
            csrf_token=csrf_token,
            token_type="bearer",  # nosec B106 - Not a password, it's OAuth2 token type
            user=user_dto,
            message="Access token renovado exitosamente",
            device_id=device_id,
        )

    async def _usa_el_dispositivo(
        self, request: RefreshAccessTokenRequestDTO, dispositivo: UserDevice
    ) -> str:
        """Apunta el uso del dispositivo de este refresco, el de su token, y da su id.

        El del token manda: antes se registraba otro por su cuenta (sin cookie y con IP
        nueva, uno nuevo y huérfano), y el `did` y la cookie apuntaban a dos distintos
        (/code-review, BE #737). La ruta le vuelve a poner la cookie siempre.
        """
        async with self._uow:
            dispositivo.update_last_used()
            dispositivo.update_ip_address(request.ip_address or UNRESOLVED_IP_PLACEHOLDER)
            dispositivo.update_country(request.country_code)
            dispositivo.update_installed_app(request.installed_app)
            if request.user_agent:
                dispositivo.update_user_agent(request.user_agent)
            await self._uow.user_devices.save(dispositivo)
        return str(dispositivo.id.value)

    async def _rechaza_si_no_vale(self, refresh_token_entity: RefreshToken) -> None:
        """Rechaza, con su motivo, el token revocado o caducado en BD."""
        if refresh_token_entity.revoked:
            # Revocado por 24 h sin uso sigue siendo el final normal: lo vuelve a
            # mandar otra pestaña, o la cookie que se quedó (/code-review, 5 nov)
            dispositivo = await self._dispositivo_del_token(refresh_token_entity)
            # Solo si el dispositivo sigue activo: uno revocado es un rechazo, no un
            # final normal, aunque además lleve 24 h sin usarse (revisor de la PR)
            if dispositivo is not None and dispositivo.is_active and dispositivo.is_idle():
                raise RefreshRejectedError(RefreshRejection.SESSION_IDLE)
            # Refresh token fue revocado explícitamente (logout)
            raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_REVOKED)

        if refresh_token_entity.is_expired():
            # Refresh token expiró (aunque JWT aún no lo detectara)
            raise RefreshRejectedError(RefreshRejection.REFRESH_TOKEN_EXPIRED)

    async def _dispositivo_del_token(self, refresh_token_entity: RefreshToken) -> UserDevice | None:
        if refresh_token_entity.device_id is None:
            return None
        return await self._uow.user_devices.find_by_id(refresh_token_entity.device_id)
