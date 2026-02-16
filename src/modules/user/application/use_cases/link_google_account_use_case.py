"""
Link Google Account Use Case - Application Layer

Caso de uso para vincular una cuenta de Google a un usuario autenticado.
"""

from src.modules.user.application.dto.oauth_dto import (
    LinkGoogleAccountRequestDTO,
    LinkGoogleAccountResponseDTO,
)
from src.modules.user.application.ports.google_oauth_service_interface import (
    IGoogleOAuthService,
)
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_id import UserId


class LinkGoogleAccountUseCase:
    """
    Vincula una cuenta de Google a un usuario autenticado existente.

    Validaciones:
    - La cuenta Google no debe estar vinculada a otro usuario
    - El usuario actual no debe tener ya una cuenta Google vinculada
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        google_oauth_service: IGoogleOAuthService,
    ):
        self._uow = uow
        self._google_oauth_service = google_oauth_service

    async def execute(
        self, request: LinkGoogleAccountRequestDTO, user_id: str
    ) -> LinkGoogleAccountResponseDTO:
        """
        Vincula cuenta Google al usuario autenticado.

        Args:
            request: DTO con authorization_code
            user_id: ID del usuario autenticado (de JWT)

        Returns:
            LinkGoogleAccountResponseDTO con confirmación

        Raises:
            ValueError: Si la cuenta ya está vinculada a otro usuario o el usuario ya tiene Google
        """
        google_info = await self._google_oauth_service.exchange_code_for_user_info(
            request.authorization_code
        )

        uid = UserId(user_id)

        # Lecturas y escritura en una sola transacción (previene TOCTOU)
        async with self._uow:
            # Verificar que la cuenta Google no está vinculada a otro usuario
            existing = await self._uow.oauth_accounts.find_by_provider_and_provider_user_id(
                OAuthProvider.GOOGLE, google_info.google_user_id
            )
            if existing:
                raise ValueError("This Google account is already linked to another user")

            # Verificar que el usuario no tiene ya un link Google
            existing_for_user = await self._uow.oauth_accounts.find_by_user_id_and_provider(
                uid, OAuthProvider.GOOGLE
            )
            if existing_for_user:
                raise ValueError("You already have a Google account linked")

            # Crear y persistir la vinculación
            oauth_account = UserOAuthAccount.create(
                user_id=uid,
                provider=OAuthProvider.GOOGLE,
                provider_user_id=google_info.google_user_id,
                provider_email=google_info.email,
            )
            await self._uow.oauth_accounts.save(oauth_account)

        return LinkGoogleAccountResponseDTO(
            message="Google account linked successfully",
            provider=OAuthProvider.GOOGLE.value,
            provider_email=google_info.email,
        )
