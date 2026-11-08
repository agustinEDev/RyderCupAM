"""
Unlink Google Account Use Case - Application Layer

Caso de uso para desvincular una cuenta de Google de un usuario autenticado.
"""

from datetime import datetime

from src.modules.user.application.dto.oauth_dto import UnlinkGoogleAccountResponseDTO
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.application.services.cierra_lo_que_no_se_probo import avisa_de_google
from src.modules.user.application.services.registra_sin_romper import registra_sin_romper
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

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        *,
        email_service: IEmailService,
        security_audit: ISecurityAuditLogger,
    ):
        self._uow = uow
        # El aviso a la cuenta (BE #753)
        self._email_service = email_service
        # El rastro en el log de seguridad, como al vincular
        self._security_audit = security_audit

    async def execute(
        self,
        user_id: str,
        *,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
    ) -> UnlinkGoogleAccountResponseDTO:
        """
        Desvincula cuenta Google del usuario.

        Args:
            user_id: ID del usuario autenticado (de JWT)
            ip_address: IP de la petición, para el log de seguridad
            user_agent: Navegador de la petición, para el log de seguridad

        Returns:
            UnlinkGoogleAccountResponseDTO con confirmación

        Raises:
            ValueError: Si no tiene cuenta Google vinculada o si es su único método de auth
        """
        uid = UserId(user_id)

        # Lecturas, validaciones, delete y evento en una sola transacción
        async with self._uow:
            # Primero la fila bloqueada: una toma a la vez quita la contraseña, y dos
            # desvinculaciones a la vez no dicen las dos «hecho» (tabla de caminos de
            # #749; CodeRabbit en #752)
            user = await self._uow.users.find_by_id_for_update(uid)
            if not user:
                raise ValueError("User not found")

            # Buscar OAuth account, ya con la fila bloqueada
            oauth_account = await self._uow.oauth_accounts.find_by_user_id_and_provider(
                uid, OAuthProvider.GOOGLE
            )
            if not oauth_account:
                raise ValueError("No Google account linked to this user")

            # Guard: verificar que el usuario tiene password

            if not user.has_password:
                raise ValueError(
                    "Cannot unlink Google account: it is your only authentication method. "
                    "Set a password first."
                )

            # Eliminar OAuth account y emitir evento atómicamente
            await self._uow.oauth_accounts.delete(oauth_account)
            user.record_google_unlinked(
                provider=OAuthProvider.GOOGLE.value,
                unlinked_at=datetime.now(),
            )
            await self._uow.users.save(user)

        # Ya guardado, al log con la red: sin él, quitar el Google de otro con una sesión
        # robada no dejaba rastro. Un fallo del log no cambia la respuesta
        registra_sin_romper(
            "Google unlink",
            lambda: self._security_audit.log_google_account_unlinked(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            ),
        )

        await avisa_de_google(self._email_service, user, linked=False)

        return UnlinkGoogleAccountResponseDTO(
            message="Google account unlinked successfully",
            provider=OAuthProvider.GOOGLE.value,
        )
