"""Caso de Uso: (Des)activar una cuenta de usuario (panel de administración)."""

import logging
from collections.abc import Callable

from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.application.services.revoca_sus_sesiones import revoca_sus_sesiones
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

    async def execute(
        self,
        user_id_str: str,
        is_active: bool,
        actor_user_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """(Des)activa la cuenta y lo deja en el log de seguridad.

        Desactivarla revoca sus sesiones. Reactivarla revoca también las que se
        hubieran colado (un login a la vez que la desactivación): tiene que volver a
        entrar (auditoría OWASP).
        """
        if not is_active and user_id_str == actor_user_id:
            raise ValueError("Admins cannot deactivate their own account")

        user_id = UserId(user_id_str)
        revocados: tuple[int, int] | None = None
        reactivada: int | None = None

        async with self._uow:
            # Con la fila bloqueada: dos cambios del administrador a la vez no se
            # pisan. Lo que un login cuele a la vez se revoca al reactivar
            user = await self._uow.users.find_by_id_for_update(user_id)
            if not user:
                raise UserNotFoundError(f"User not found: {user_id_str}")

            if is_active:
                if not user.is_active:
                    user.reactivate(reactivated_by_user_id=actor_user_id)
                    # Lo que se colara (un login a la vez que la desactivación), fuera
                    reactivada = (await revoca_sus_sesiones(self._uow, user_id))[1]
            elif user.is_active:
                user.deactivate(deactivated_by_user_id=actor_user_id)
                revocados = await revoca_sus_sesiones(self._uow, user_id)

            await self._uow.users.save(user)

        contexto = (ip_address or "unknown", user_agent or "unknown")
        if revocados is not None:
            self._apunta(
                self._security_audit.log_account_deactivated,
                user_id=actor_user_id,
                deactivated_user_id=user_id_str,
                devices_revoked=revocados[0],
                tokens_revoked=revocados[1],
                ip_address=contexto[0],
                user_agent=contexto[1],
            )
        if reactivada is not None:
            self._apunta(
                self._security_audit.log_account_reactivated,
                user_id=actor_user_id,
                reactivated_user_id=user_id_str,
                tokens_revoked=reactivada,
                ip_address=contexto[0],
                user_agent=contexto[1],
            )

    @staticmethod
    def _apunta(registra: Callable[..., None], **datos: object) -> None:
        """Al log de seguridad, ya guardada: si el log falla, el cambio vale igual."""
        try:
            registra(**datos)
        except Exception as e:
            # Solo el tipo del error, no su mensaje
            logger.error("Account status audit event failed: %s", type(e).__name__)
