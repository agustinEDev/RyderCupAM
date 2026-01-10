"""
Unlock Account Use Case

Caso de uso para desbloquear manualmente una cuenta bloqueada (solo Admin).
Account Lockout (v1.13.0): Permite desbloquear cuentas antes de expiración de 30 min.
"""

from src.modules.user.application.dto.user_dto import (
    UnlockAccountRequestDTO,
    UnlockAccountResponseDTO,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class UnlockAccountUseCase:
    """
    Caso de uso para desbloquear manualmente una cuenta bloqueada.

    Responsabilidades:
    - Verificar que el usuario existe
    - Verificar que la cuenta está bloqueada
    - Desbloquear la cuenta (resetear failed_login_attempts y locked_until)
    - Emitir AccountUnlockedEvent para auditoría

    Security (OWASP A01, A09):
    - Solo accesible por Admin (verificado en API Layer con dependency)
    - Evento de auditoría registra quién desbloqueó
    - Previene abuso de auto-desbloqueo

    Restrictions:
    - Solo Admin puede ejecutar este use case
    - La validación de rol se hace en API Layer (auth_routes.py)
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work para acceso a repositorios
        """
        self._uow = uow

    async def execute(
        self, request: UnlockAccountRequestDTO
    ) -> UnlockAccountResponseDTO:
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
        user.unlock(unlocked_by_user_id=request.unlocked_by_user_id)

        # Persistir cambios usando Unit of Work
        async with self._uow:
            await self._uow.users.save(user)
            # Commit automático al salir del contexto
            # AccountUnlockedEvent se emitirá automáticamente

        return UnlockAccountResponseDTO(
            success=True,
            message=f"Account for user {request.user_id} unlocked successfully",
            user_id=request.user_id,
            unlocked_by=request.unlocked_by_user_id,
        )
