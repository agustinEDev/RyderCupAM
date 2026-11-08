"""
Link Google Account Use Case - Application Layer

Caso de uso para vincular una cuenta de Google a un usuario autenticado.
"""

from src.modules.user.application.dto.oauth_dto import (
    LinkGoogleAccountRequestDTO,
    LinkGoogleAccountResponseDTO,
)
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.google_oauth_service_interface import (
    IGoogleOAuthService,
)
from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.application.services.cierra_lo_que_no_se_probo import avisa_de_google
from src.modules.user.application.services.registra_sin_romper import registra_sin_romper
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_id import UserId


class GoogleLinkNeedsVerifiedEmailError(ValueError):
    """Vincular Google pide el correo de la cuenta verificado.

    Sin esta regla, quien creó una cuenta con un correo ajeno, sin poder
    verificarlo, metía su propio Google y lo conservaba aunque el dueño del correo
    la recuperara (revisión de la pre-captura, #749). La ruta responde 403 con
    GOOGLE_LINK_NEEDS_VERIFIED_EMAIL.
    """


class ReauthenticationRequiredError(PermissionError):
    """
    Vincular Google pide la contraseña actual a una cuenta que la tiene (BE #753): con
    solo la sesión, una robada podía añadir un Google que sobrevive al restablecimiento.
    """


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
        *,
        security_audit: ISecurityAuditLogger,
        email_service: IEmailService,
    ):
        self._uow = uow
        self._google_oauth_service = google_oauth_service
        self._security_audit = security_audit
        self._email_service = email_service

    async def execute(
        self,
        request: LinkGoogleAccountRequestDTO,
        user_id: str,
        reautenticado: bool = False,
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
        uid = UserId(user_id)
        # Antes que gastar el código de Google
        async with self._uow:
            cuenta = await self._uow.users.find_by_id(uid)
        if cuenta is None or not cuenta.email_verified:
            raise GoogleLinkNeedsVerifiedEmailError("Verify your email before linking Google")
        # Con contraseña, la marca de haberla escrito hace poco; también antes de gastar
        # el código de Google
        if cuenta.has_password and not reautenticado:
            raise ReauthenticationRequiredError("Enter your current password first")

        google_info = await self._google_oauth_service.exchange_code_for_user_info(
            request.authorization_code
        )

        # Lecturas y escritura en una sola transacción (previene TOCTOU)
        async with self._uow:
            # Otra vez, con la fila bloqueada: un cambio de correo a la vez la habría
            # dejado sin verificar entre la primera comprobación y el vínculo
            cuenta = await self._uow.users.find_by_id_for_update(uid)
            if cuenta is None or not cuenta.email_verified:
                raise GoogleLinkNeedsVerifiedEmailError("Verify your email before linking Google")

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

        # Ya guardado, al log con la red (#750 punto 3): aquí y no en la ruta, para que
        # cualquier uso del caso de uso quede auditado, como el vínculo automático
        registra_sin_romper(
            "Google link",
            lambda: self._security_audit.log_google_account_linked(
                user_id=user_id,
                automatic=False,
                ip_address=request.ip_address or "unknown",
                user_agent=request.user_agent or "unknown",
            ),
        )

        await avisa_de_google(self._email_service, cuenta, linked=True)

        return LinkGoogleAccountResponseDTO(
            message="Google account linked successfully",
            provider=OAuthProvider.GOOGLE.value,
            provider_email=google_info.email,
        )
