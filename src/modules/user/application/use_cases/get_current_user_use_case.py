"""
Get Current User Use Case

Caso de uso para obtener el usuario actual desde un JWT token.
"""

from typing import Optional

from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


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

    async def execute(self, user_id_str: str) -> Optional[UserResponseDTO]:
        """
        Ejecuta el caso de uso.

        Args:
            user_id_str: ID del usuario en formato string

        Returns:
            UserResponseDTO si el usuario existe, None si no existe

        Example:
            >>> response = await use_case.execute("user-uuid")
            >>> if response:
            >>>     print(response.email)
        """
        try:
            user_id = UserId(user_id_str)
        except (ValueError, TypeError):
            return None

        user = await self._uow.users.find_by_id(user_id)

        if not user:
            return None

        return UserResponseDTO.model_validate(user)
