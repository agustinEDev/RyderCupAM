"""
Logout User Use Case

Caso de uso para cerrar sesión de un usuario.
Implementación evolutiva: simple ahora, preparada para blacklist después.
"""

from datetime import datetime
from typing import Optional

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

    Esta implementación está diseñada para evolucionar:
    
    Fase 1 (Actual): Logout simple con validación de usuario
    - Valida que el usuario existe
    - Registra el timestamp del logout
    - Retorna confirmación
    
    Fase 2 (Futura): Con blacklist profesional
    - Misma interface pública
    - Internamente agregará tokens a blacklist
    - Sin cambios en controllers
    
    Responsabilidades:
    - Validar que el usuario existe (del token JWT)
    - Gestionar la invalidación del token (preparado para blacklist)
    - Registrar el evento de logout para auditoría
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorio de usuarios
        """
        self._uow = uow

    async def execute(
        self, 
        request: LogoutRequestDTO, 
        user_id: str,
        token: Optional[str] = None
    ) -> Optional[LogoutResponseDTO]:
        """
        Ejecuta el caso de uso de logout.

        Args:
            request: DTO de logout (preparado para extensiones futuras)
            user_id: ID del usuario obtenido del token JWT
            token: Token JWT original (preparado para blacklist futura)

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

        # 2. Invalidar token (Fase 1: Solo preparación)
        self._invalidate_token(token, user_id)

        # 3. Registrar evento de logout para auditoría
        logout_time = datetime.now()
        user.record_logout(logout_time, token)

        # 4. Persistir cambios usando Unit of Work (Clean Architecture)
        # El UoW maneja automáticamente la transacción y publicación de eventos
        async with self._uow:
            await self._uow.users.save(user)

        return LogoutResponseDTO(
            message="Logout exitoso",
            logged_out_at=logout_time
        )

    def _invalidate_token(self, token: Optional[str], _user_id: str) -> None:
        """
        Invalida el token de acceso.
        
        Fase 1 (Actual): No hace nada real - logout del lado cliente
        Fase 2 (Futura): Agregará el token a blacklist
        
        Args:
            token: Token JWT a invalidar
            _user_id: ID del usuario para logging (preparado para Fase 2)
        """
        # Fase 1: Implementación simple - logout del lado cliente
        # El token permanece técnicamente válido hasta su expiración
        
        # Preparado para Fase 2: Blacklist implementation
        # await self._blacklist_service.add_token(token)
        
        if token:
            # Fase 1: Solo validación de que el token existe
            pass

