"""
Update Profile Use Case - Application Layer

Caso de uso para actualizar la información personal de un usuario (nombre y apellidos).
NO requiere validación de contraseña, solo autenticación JWT.
"""

from src.modules.user.application.dto.user_dto import (
    UpdateProfileRequestDTO,
    UpdateProfileResponseDTO,
    UserResponseDTO
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import UserUnitOfWorkInterface
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.value_objects.user_id import UserId


class UpdateProfileUseCase:
    """
    Caso de uso: Actualizar información personal del usuario.

    Permite a un usuario autenticado actualizar su nombre y/o apellidos
    sin necesidad de proporcionar su contraseña actual.
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        """
        Inicializa el caso de uso con sus dependencias.

        Args:
            uow: Unit of Work para manejar transacciones
        """
        self._uow = uow

    async def execute(self, user_id: str, request: UpdateProfileRequestDTO) -> UpdateProfileResponseDTO:
        """
        Ejecuta el caso de uso de actualización de perfil.

        Args:
            user_id: ID del usuario autenticado (del JWT token)
            request: DTO con los datos a actualizar

        Returns:
            UpdateProfileResponseDTO con el usuario actualizado

        Raises:
            UserNotFoundError: Si el usuario no existe
            ValueError: Si los datos no son válidos
        """
        async with self._uow:
            # Buscar usuario
            user_id_vo = UserId(user_id)
            user = await self._uow.users.find_by_id(user_id_vo)
            if not user:
                raise UserNotFoundError(f"User with id {user_id} not found")

            # Actualizar perfil (entity valida y emite eventos)
            user.update_profile(
                first_name=request.first_name,
                last_name=request.last_name
            )

            # Guardar cambios
            await self._uow.users.save(user)

            # Context manager hace commit automático y publica eventos

        # Construir respuesta
        return UpdateProfileResponseDTO(
            user=UserResponseDTO.model_validate(user),
            message="Profile updated successfully"
        )
