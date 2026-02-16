"""
Get Current User Use Case

Caso de uso para obtener el usuario actual desde un JWT token.
"""

from src.modules.user.application.dto.user_dto import UserResponseDTO
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
            UserResponseDTO si el usuario existe, None si no existe
        """
        try:
            user_id = UserId(user_id_str)
        except (ValueError, TypeError, InvalidUserIdError):
            return None

        user = await self._uow.users.find_by_id(user_id)

        if not user:
            return None

        # Consultar proveedores OAuth vinculados
        oauth_accounts = await self._uow.oauth_accounts.find_by_user_id(user_id)
        auth_providers = [account.provider.value for account in oauth_accounts]

        dto = UserResponseDTO.model_validate(user)
        dto.auth_providers = auth_providers

        return dto
