"""
Logout User Use Case

Caso de uso para cerrar sesión de un usuario.
Session Timeout (v1.8.0): Revoca todos los refresh tokens del usuario.
Security Logging (v1.8.0): Registra logout con cantidad de tokens revocados.
"""

from datetime import datetime

from src.modules.user.application.dto.user_dto import (
    LogoutRequestDTO,
    LogoutResponseDTO,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.logging.security_logger import get_security_logger


class LogoutUserUseCase:
    """
    Caso de uso para logout de usuario.

    Responsabilidades:
    - Validar que el usuario existe (del token JWT)
    - Revocar todos los refresh tokens del usuario (v1.8.0)
    - Registrar el evento de logout para auditoría
    - Retornar confirmación

    Session Timeout (v1.8.0):
    - Revoca todos los refresh tokens activos del usuario
    - El access token sigue técnicamente válido hasta expiración (15 min)
    - Frontend debe eliminar cookies httpOnly de access y refresh tokens
    - OWASP A01: Previene reuso de refresh tokens después de logout
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorios (users + refresh_tokens)
        """
        self._uow = uow

    async def execute(
        self, request: LogoutRequestDTO, user_id: str, token: str | None = None
    ) -> LogoutResponseDTO | None:
        """
        Ejecuta el caso de uso de logout.

        Args:
            request: DTO de logout con contexto de seguridad (IP, User-Agent)
            user_id: ID del usuario obtenido del token JWT
            token: Token JWT original (actualmente no usado)

        Returns:
            LogoutResponseDTO con confirmación y timestamp
            None si el usuario no existe

        Security Logging (v1.8.0):
            - Registra logout con cantidad de refresh tokens revocados
            - Registra revocación de tokens por logout
            - Severity LOW (acción normal)

        Example:
            >>> request = LogoutRequestDTO(
            ...     ip_address="192.168.1.1",
            ...     user_agent="Mozilla/5.0..."
            ... )
            >>> response = await use_case.execute(request, "user-123", "jwt-token")
            >>> print(response.message)  # "Logout exitoso"
        """
        # Obtener security logger
        security_logger = get_security_logger()

        # Valores por defecto para security logging
        ip_address = request.ip_address or "unknown"
        user_agent = request.user_agent or "unknown"

        # 1. Verificar que el usuario existe
        user_id_vo = UserId(user_id)
        user = await self._uow.users.find_by_id(user_id_vo)

        if not user:
            return None

        # 2. Registrar evento de logout para auditoría (dominio)
        logout_time = datetime.now()
        user.record_logout(logout_time, token)

        # 3. Obtener todos los refresh tokens del usuario (v1.8.0)
        # Esto previene que el usuario pueda renovar su access token después del logout
        refresh_tokens = await self._uow.refresh_tokens.find_all_by_user(user_id_vo)
        tokens_revoked_count = 0

        # 4. Persistir cambios usando Unit of Work (Clean Architecture)
        # CRÍTICO: Todas las operaciones dentro del contexto UoW para garantizar atomicidad
        # Si algo falla, TODO se revierte (rollback). Si todo OK, TODO se guarda (commit).
        async with self._uow:
            # Revocar tokens dentro de la transacción
            for refresh_token in refresh_tokens:
                if not refresh_token.revoked:
                    refresh_token.revoke()
                    await self._uow.refresh_tokens.save(refresh_token)
                    tokens_revoked_count += 1

            # Guardar usuario dentro de la misma transacción
            await self._uow.users.save(user)
            # Commit automático al salir del contexto (atomicidad garantizada)

        # 5. Security Logging: Logout exitoso
        security_logger.log_logout(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            refresh_tokens_revoked=tokens_revoked_count,
        )

        # 6. Security Logging: Revocación de refresh tokens
        if tokens_revoked_count > 0:
            security_logger.log_refresh_token_revoked(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                tokens_revoked_count=tokens_revoked_count,
                reason="logout",
            )

        return LogoutResponseDTO(message="Logout exitoso", logged_out_at=logout_time)
