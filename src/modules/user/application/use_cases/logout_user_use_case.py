"""
Logout User Use Case

Caso de uso para cerrar sesión de un usuario.
Session Timeout (v1.8.0): Revoca todos los refresh tokens del usuario.
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
        self,
        request: LogoutRequestDTO,
        user_id: str,
        token: str | None = None
    ) -> LogoutResponseDTO | None:
        """
        Ejecuta el caso de uso de logout.

        Args:
            request: DTO de logout (preparado para extensiones futuras)
            user_id: ID del usuario obtenido del token JWT
            token: Token JWT original (actualmente no usado)

        Returns:
            LogoutResponseDTO con confirmación y timestamp
            None si el usuario no existe

        Example:
            >>> request = LogoutRequestDTO()
            >>> response = await use_case.execute(request, "user-123", "jwt-token")
            >>> print(response.message)  # "Logout exitoso"
        """
        # 1. Verificar que el usuario existe
        user_id_vo = UserId(user_id)
        user = await self._uow.users.find_by_id(user_id_vo)

        if not user:
            return None

        # 2. Registrar evento de logout para auditoría
        logout_time = datetime.now()
        user.record_logout(logout_time, token)

        # 3. Revocar todos los refresh tokens del usuario (v1.8.0)
        # Esto previene que el usuario pueda renovar su access token después del logout
        refresh_tokens = await self._uow.refresh_tokens.find_all_by_user(user_id_vo)

        for refresh_token in refresh_tokens:
            if not refresh_token.revoked:
                refresh_token.revoke()
                await self._uow.refresh_tokens.save(refresh_token)

        # 4. Persistir cambios usando Unit of Work (Clean Architecture)
        # El UoW maneja automáticamente la transacción y publicación de eventos
        async with self._uow:
            await self._uow.users.save(user)
            # Los refresh tokens ya fueron actualizados, commit automático

        return LogoutResponseDTO(
            message="Logout exitoso",
            logged_out_at=logout_time
        )

