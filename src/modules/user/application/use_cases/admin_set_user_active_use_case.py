"""Caso de Uso: (Des)activar una cuenta de usuario (panel de administración)."""

import logging

from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class AdminSetUserActiveUseCase:
    """
    Desactiva o reactiva la cuenta de un usuario (solo Admin).

    Una cuenta desactivada no puede iniciar sesión pero conserva todos sus
    datos (torneos, partidas, amistades) intactos — acción reversible.

    Desactivar también la deja sin sesión al momento (BE #744): sus dispositivos y
    sus tokens de refresco se revocan en la misma transacción, y queda en el log de
    seguridad. Reactivar no devuelve esas sesiones: tiene que volver a entrar.
    """

    def __init__(self, uow: UserUnitOfWorkInterface, security_audit: ISecurityAuditLogger):
        """
        Args:
            uow: Unit of Work (users, user_devices y refresh_tokens)
            security_audit: El log de seguridad, donde queda cada desactivación
        """
        self._uow = uow
        self._security_audit = security_audit

    async def execute(self, user_id_str: str, is_active: bool, actor_user_id: str) -> None:
        """(Des)activa la cuenta. Desactivarla revoca sus sesiones y lo deja en el log."""
        if not is_active and user_id_str == actor_user_id:
            raise ValueError("Admins cannot deactivate their own account")

        user_id = UserId(user_id_str)
        revocados: tuple[int, int] | None = None

        async with self._uow:
            user = await self._uow.users.find_by_id(user_id)
            if not user:
                raise UserNotFoundError(f"User not found: {user_id_str}")

            if is_active:
                if not user.is_active:
                    user.reactivate(reactivated_by_user_id=actor_user_id)
            elif user.is_active:
                user.deactivate(deactivated_by_user_id=actor_user_id)
                revocados = await self._revoca_sus_sesiones(user_id)

            await self._uow.users.save(user)

        if revocados is not None:
            self._apunta_la_desactivacion(user_id_str, actor_user_id, *revocados)

    async def _revoca_sus_sesiones(self, user_id: UserId) -> tuple[int, int]:
        """Revoca sus dispositivos y sus tokens de refresco. Devuelve cuántos de cada."""
        dispositivos = await self._uow.user_devices.find_active_by_user(user_id)
        for dispositivo in dispositivos:
            dispositivo.revoke()
            await self._uow.user_devices.save(dispositivo)
        tokens = await self._uow.refresh_tokens.revoke_all_for_user(user_id)
        return len(dispositivos), tokens

    def _apunta_la_desactivacion(
        self, user_id: str, actor: str, dispositivos: int, tokens: int
    ) -> None:
        """Al log de seguridad, ya guardada: si el log falla, la desactivación vale igual."""
        try:
            self._security_audit.log_account_deactivated(
                user_id=actor,
                deactivated_user_id=user_id,
                devices_revoked=dispositivos,
                tokens_revoked=tokens,
            )
        except Exception as e:
            # Solo el tipo del error, no su mensaje
            logger.error("Account deactivation audit event failed: %s", type(e).__name__)
