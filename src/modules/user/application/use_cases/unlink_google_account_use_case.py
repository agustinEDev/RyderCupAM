"""
Unlink Google Account Use Case - Application Layer

Caso de uso para desvincular una cuenta de Google de un usuario autenticado.
"""

from datetime import datetime

from src.modules.user.application.dto.oauth_dto import UnlinkGoogleAccountResponseDTO
from src.modules.user.domain.events.google_account_unlinked_event import (
    GoogleAccountUnlinkedEvent,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_id import UserId


class UnlinkGoogleAccountUseCase:
    """
    Desvincula la cuenta de Google de un usuario autenticado.

    Guard: No se permite desvincular si el usuario no tiene password,
    ya que sería su único método de autenticación.
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, user_id: str) -> UnlinkGoogleAccountResponseDTO:
        """
        Desvincula cuenta Google del usuario.

        Args:
            user_id: ID del usuario autenticado (de JWT)

        Returns:
            UnlinkGoogleAccountResponseDTO con confirmación

        Raises:
            ValueError: Si no tiene cuenta Google vinculada o si es su único método de auth
        """
        uid = UserId(user_id)

        # Buscar OAuth account
        oauth_account = await self._uow.oauth_accounts.find_by_user_id_and_provider(
            uid, OAuthProvider.GOOGLE
        )
        if not oauth_account:
            raise ValueError("No Google account linked to this user")

        # Guard: verificar que el usuario tiene password
        user = await self._uow.users.find_by_id(uid)
        if not user:
            raise ValueError("User not found")

        if not user.has_password():
            raise ValueError(
                "Cannot unlink Google account: it is your only authentication method. "
                "Set a password first."
            )

        # Eliminar OAuth account
        async with self._uow:
            await self._uow.oauth_accounts.delete(oauth_account)

        # Emitir evento en el usuario
        user._add_domain_event(
            GoogleAccountUnlinkedEvent(
                user_id=str(uid.value),
                provider=OAuthProvider.GOOGLE.value,
                unlinked_at=datetime.now(),
            )
        )

        return UnlinkGoogleAccountResponseDTO(
            message="Google account unlinked successfully",
            provider=OAuthProvider.GOOGLE.value,
        )
