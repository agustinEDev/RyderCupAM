"""
Accept Terms Use Case - Application Layer

El usuario autenticado acepta la versión vigente de los Términos de uso.
"""

from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.terms_of_service import current_terms_version
from src.modules.user.domain.value_objects.user_id import UserId


class AcceptTermsUseCase:
    """
    Caso de uso: aceptar la versión vigente de los Términos.

    Idempotente: si ya la tenía aceptada no cambia nada, tampoco la fecha. La
    respuesta es la misma que la de current-user, para que el cliente pueda
    seguir con ella sin volver a pedirla.
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, user_id: str) -> UserResponseDTO:
        """
        Acepta los Términos vigentes en nombre de ese usuario.

        Args:
            user_id: Id del usuario autenticado

        Returns:
            El usuario, ya con los Términos aceptados

        Raises:
            UserNotFoundError: Si no existe
        """
        async with self._uow:
            user_id_vo = UserId(user_id)
            # Con bloqueo, como las demás mutaciones del propio usuario
            user = await self._uow.users.find_by_id_for_update(user_id_vo)
            if not user:
                raise UserNotFoundError(f"User with id {user_id} not found")

            if user.accept_terms(current_terms_version()):
                await self._uow.users.save(user)

            oauth_accounts = await self._uow.oauth_accounts.find_by_user_id(user_id_vo)

        dto = UserResponseDTO.model_validate(user)
        dto.auth_providers = [account.provider.value for account in oauth_accounts]
        return dto
