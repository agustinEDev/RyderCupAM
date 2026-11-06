"""
Unlock Account Use Case

Caso de uso para desbloquear manualmente una cuenta bloqueada (solo Admin).
Account Lockout (v1.13.0): Permite desbloquear cuentas antes de expiración de 30 min.
"""

import logging

from src.modules.user.application.dto.user_dto import (
    UnlockAccountRequestDTO,
    UnlockAccountResponseDTO,
)
from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class UnlockAccountUseCase:
    """
    Caso de uso para desbloquear manualmente una cuenta bloqueada.

    Responsabilidades:
    - Verificar que el usuario existe
    - Verificar que la cuenta está bloqueada
    - Desbloquear la cuenta (resetear failed_login_attempts y locked_until)
    - Dejar el desbloqueo en el log de seguridad (hotfix 2.50.1)

    Security (OWASP A01, A09):
    - Solo accesible por Admin (lo comprueba la ruta con require_admin)
    - El log de seguridad registra quién desbloqueó a quién y desde dónde
    - Previene abuso de auto-desbloqueo

    Restrictions:
    - Solo Admin puede ejecutar este use case
    - La validación de rol se hace en API Layer (auth_routes.py)
    """

    def __init__(self, uow: UserUnitOfWorkInterface, security_audit: ISecurityAuditLogger):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorios
        """
        self._uow = uow
        # El log de seguridad, por su puerto: un caso de uso no importa infraestructura
        self._security_audit = security_audit

    async def execute(self, request: UnlockAccountRequestDTO) -> UnlockAccountResponseDTO:
        """
        Ejecuta el caso de uso de desbloqueo de cuenta.

        Args:
            request: DTO con user_id (a desbloquear) y unlocked_by_user_id (admin)

        Returns:
            UnlockAccountResponseDTO con resultado de la operación

        Raises:
            ValueError: Si el usuario no existe o la cuenta no está bloqueada

        Example:
            >>> request = UnlockAccountRequestDTO(
            ...     user_id="user-uuid-123",
            ...     unlocked_by_user_id="admin-uuid-456"
            ... )
            >>> response = await use_case.execute(request)
            >>> print(response.success)  # True
            >>> print(response.message)  # "Account unlocked successfully"
        """
        # Buscar usuario por ID
        user_id = UserId(request.user_id)
        user = await self._uow.users.find_by_id(user_id)

        if not user:
            raise ValueError(f"User with ID {request.user_id} not found")

        # Desbloquear cuenta (lanza ValueError si no está bloqueada)
        fallos = user.failed_login_attempts
        user.unlock(unlocked_by_user_id=request.unlocked_by_user_id)

        # Persistir cambios usando Unit of Work
        async with self._uow:
            await self._uow.users.save(user)
            # Commit automático al salir del contexto

        # Al log de seguridad (hotfix 2.50.1): el AccountUnlockedEvent del dominio no
        # lo leía nadie. Ya está guardado: si el log falla, se responde bien igual.
        # Solo el tipo del error, no su mensaje
        try:
            self._security_audit.log_account_unlocked(
                user_id=request.unlocked_by_user_id,
                unlocked_user_id=request.user_id,
                ip_address=request.ip_address or "unknown",
                user_agent=request.user_agent or "unknown",
                previous_failed_attempts=fallos,
            )
        except Exception as e:
            logger.error("Account unlock audit event failed: %s", type(e).__name__)

        return UnlockAccountResponseDTO(
            success=True,
            message=f"Account for user {request.user_id} unlocked successfully",
            user_id=request.user_id,
            unlocked_by=request.unlocked_by_user_id,
        )
