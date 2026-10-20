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


async def build_current_user_response(
    uow: UserUnitOfWorkInterface, user: User, auth_providers: list[str] | None = None
) -> UserResponseDTO:
    """
    El usuario como lo ve él mismo.

    Args:
        uow: Unit of Work, para leer sus cuentas OAuth
        user: El usuario, ya cargado
        auth_providers: Sus proveedores OAuth si ya se conocen (p. ej. del
            usuario de la sesión): así no se vuelven a leer

    Returns:
        UserResponseDTO con `auth_providers` relleno (`has_password` y los
        Términos salen de las propiedades del usuario)
    """
    if auth_providers is None:
        oauth_accounts = await uow.oauth_accounts.find_by_user_id(user.id)
        auth_providers = [account.provider.value for account in oauth_accounts]
    dto = UserResponseDTO.model_validate(user)
    dto.auth_providers = list(auth_providers)
    return dto
