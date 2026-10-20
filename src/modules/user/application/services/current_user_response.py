"""
La respuesta «quién soy» del usuario autenticado.

Un solo sitio para current-user y para accept-terms (que devuelve lo mismo),
para que las dos no puedan divergir: el DTO del usuario más los proveedores
OAuth que tiene vinculados.
"""

from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)


async def build_current_user_response(uow: UserUnitOfWorkInterface, user: User) -> UserResponseDTO:
    """
    El usuario como lo ve él mismo.

    Args:
        uow: Unit of Work, para leer sus cuentas OAuth
        user: El usuario, ya cargado

    Returns:
        UserResponseDTO con `auth_providers` relleno (`has_password` y los
        Términos salen de las propiedades del usuario)
    """
    oauth_accounts = await uow.oauth_accounts.find_by_user_id(user.id)
    dto = UserResponseDTO.model_validate(user)
    dto.auth_providers = [account.provider.value for account in oauth_accounts]
    return dto
