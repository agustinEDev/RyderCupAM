"""
Get Current User Use Case

Caso de uso para obtener el usuario actual desde un JWT token.
"""

from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.application.services.current_user_response import (
    build_current_user_response,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import InvalidUserIdError, UserId


class GetCurrentUserUseCase:
    """
    Caso de uso para obtener usuario actual.

    Responsabilidades:
    - Buscar usuario por ID
    - Retornar datos del usuario o None
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorio de usuarios
        """
        self._uow = uow

    async def execute(self, user_id_str: str) -> UserResponseDTO | None:
        """
        Ejecuta el caso de uso.

        Busca el usuario por ID y enriquece la respuesta con:
        - auth_providers: lista de proveedores OAuth vinculados
        - has_password: recogido automáticamente por model_validate (@property)

        Args:
            user_id_str: ID del usuario en formato string

        Returns:
            UserResponseDTO si el usuario existe y está activo; si no, None
        """
        try:
            user_id = UserId(user_id_str)
        except (ValueError, TypeError, InvalidUserIdError):
            return None

        user = await self._uow.users.find_by_id(user_id)

        # Una cuenta desactivada no tiene sesión (BE #744): su token de acceso deja de
        # valer en la siguiente petición, sin esperar a que caduque
        if not user or not user.is_active:
            return None

        # La misma respuesta que accept-terms: se construye en un solo sitio
        return await build_current_user_response(self._uow, user)
