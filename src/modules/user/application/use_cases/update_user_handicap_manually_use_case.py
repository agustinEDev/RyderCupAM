"""
Update User Handicap Manually Use Case - Application Layer

Caso de uso para actualizar el hándicap de un usuario manualmente,
sin consultar servicios externos.
"""

from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class UpdateUserHandicapManuallyUseCase:
    """
    Caso de uso para actualizar el hándicap de un usuario manualmente.

    Este caso de uso NO consulta servicios externos (RFEG).
    Es útil para:
    - Correcciones manuales por parte de administradores
    - Actualización de hándicaps de jugadores no federados
    - Ajustes temporales para competiciones específicas

    El flujo es:
    1. Buscar el usuario en el repositorio
    2. Actualizar el hándicap con el valor proporcionado
    3. Persistir los cambios
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        """
        Inicializa el caso de uso con sus dependencias.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(self, user_id: UserId, handicap_value: float) -> UserResponseDTO | None:
        """
        Actualiza el hándicap de un usuario con un valor manual.

        Args:
            user_id: ID del usuario a actualizar
            handicap_value: Nuevo valor del hándicap

        Returns:
            DTO del usuario actualizado o None si no existe

        Raises:
            ValueError: Si el hándicap no está en el rango válido (-10.0 a 54.0)
        """
        async with self._uow:
            # 1. Obtener el usuario
            user = await self._uow.users.find_by_id(user_id)
            if not user:
                return None

            # 2. Actualizar hándicap (el método update_handicap ya valida el rango)
            user.update_handicap(handicap_value)

            # 3. Persistir cambios
            await self._uow.users.save(user)

            # El context manager (__aexit__) hace commit automático y publica eventos

        return UserResponseDTO.model_validate(user)
