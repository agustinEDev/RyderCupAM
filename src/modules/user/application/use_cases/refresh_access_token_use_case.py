"""
Refresh Access Token Use Case

Caso de uso para renovar el access token usando un refresh token válido.
Implementa el patrón Session Timeout (OWASP A01/A02 - v1.8.0).
Security Logging (v1.8.0): Registra uso de refresh tokens.
CSRF Protection (v1.13.0): Genera nuevo token CSRF al renovar access token.
"""

from src.config.csrf_config import generate_csrf_token
from src.modules.user.application.dto.user_dto import (
    RefreshAccessTokenRequestDTO,
    RefreshAccessTokenResponseDTO,
    UserResponseDTO,
)
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import InvalidUserIdError, UserId
from src.shared.infrastructure.logging.security_logger import get_security_logger


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

    def __init__(self, uow: UserUnitOfWorkInterface, token_service: ITokenService):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorios (users, refresh_tokens)
            token_service: Servicio para validación y generación de tokens JWT
        """
        self._uow = uow
        self._token_service = token_service

    async def execute(  # noqa: PLR0911
        self, request: RefreshAccessTokenRequestDTO, refresh_token_jwt: str
    ) -> RefreshAccessTokenResponseDTO | None:
        """
        Ejecuta el caso de uso de renovación de access token.

        Args:
            request: DTO de entrada con contexto de seguridad (IP, User-Agent)
            refresh_token_jwt: Refresh token JWT obtenido de la cookie httpOnly

        Returns:
            RefreshAccessTokenResponseDTO con nuevo access token si el refresh token es válido
            None si el refresh token es inválido, revocado o el usuario no existe

        Security Logging (v1.8.0):
            - Registra uso exitoso de refresh token
            - Severity LOW (acción normal de renovación)

        Raises:
            None - Retorna None en caso de error para que el endpoint retorne 401

        Example:
            >>> request = RefreshAccessTokenRequestDTO(
            ...     ip_address="192.168.1.1",
            ...     user_agent="Mozilla/5.0..."
            ... )
            >>> response = await use_case.execute(request, "eyJ...")
            >>> if response:
            >>>     print(response.access_token)  # Nuevo token válido por 15 min
        """
        # Obtener security logger
        security_logger = get_security_logger()

        # Valores por defecto para security logging
        ip_address = request.ip_address or "unknown"
        user_agent = request.user_agent or "unknown"

        # 1. Verificar que el refresh token JWT sea válido (firma + expiración)
        payload = self._token_service.verify_refresh_token(refresh_token_jwt)

        if not payload:
            # Token inválido, expirado o de tipo incorrecto
            return None

        # 2. Extraer user_id del payload
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None

        try:
            user_id = UserId(user_id_str)
        except (ValueError, TypeError, InvalidUserIdError):
            # Captura ValueError, TypeError, InvalidUserIdError
            return None

        # 3. Verificar que el refresh token NO esté revocado en base de datos
        # Nota: find_by_token_hash espera el JWT token original, NO el hash
        # El repositorio se encarga de hashear internamente
        refresh_token_entity = await self._uow.refresh_tokens.find_by_token_hash(refresh_token_jwt)

        if not refresh_token_entity:
            # Refresh token no existe en BD (nunca fue creado o ya fue eliminado)
            return None

        if refresh_token_entity.revoked:
            # Refresh token fue revocado explícitamente (logout)
            return None

        if refresh_token_entity.is_expired():
            # Refresh token expiró (aunque JWT aún no lo detectara)
            return None

        # 4. Verificar que el usuario sigue existiendo
        user = await self._uow.users.find_by_id(user_id)

        if not user:
            # Usuario fue eliminado
            return None

        # 5. Generar nuevo access token (15 minutos)
        new_access_token = self._token_service.create_access_token(data={"sub": str(user.id.value)})

        # 6. Generar nuevo token CSRF (256 bits, 15 minutos de duración)
        csrf_token = generate_csrf_token()

        # 7. Security Logging: Uso exitoso de refresh token
        security_logger.log_refresh_token_used(
            user_id=str(user.id.value),
            ip_address=ip_address,
            user_agent=user_agent,
            refresh_token_id=str(refresh_token_entity.id.value),
            new_access_token_created=True,
        )

        # 8. Preparar respuesta
        user_dto = UserResponseDTO.model_validate(user)

        return RefreshAccessTokenResponseDTO(
            access_token=new_access_token,
            csrf_token=csrf_token,
            token_type="bearer",  # nosec B106 - Not a password, it's OAuth2 token type
            user=user_dto,
            message="Access token renovado exitosamente",
        )
