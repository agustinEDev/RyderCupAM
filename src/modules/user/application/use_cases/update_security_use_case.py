"""
Update Security Use Case - Application Layer

Caso de uso para actualizar datos de seguridad del usuario (email y/o password).
Requiere validación de contraseña actual para autorizar los cambios.
"""

from src.modules.user.application.dto.user_dto import (
    UpdateSecurityRequestDTO,
    UpdateSecurityResponseDTO,
    UserResponseDTO
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import UserUnitOfWorkInterface
from src.modules.user.domain.errors.user_errors import (
    UserNotFoundError,
    InvalidCredentialsError,
    DuplicateEmailError
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.domain.value_objects.email import Email


class UpdateSecurityUseCase:
    """
    Caso de uso: Actualizar datos de seguridad del usuario.

    Permite a un usuario autenticado actualizar su email y/o password,
    requiriendo verificación de la contraseña actual.
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        """
        Inicializa el caso de uso con sus dependencias.

        Args:
            uow: Unit of Work para manejar transacciones
        """
        self._uow = uow

    async def execute(self, user_id: str, request: UpdateSecurityRequestDTO) -> UpdateSecurityResponseDTO:
        """
        Ejecuta el caso de uso de actualización de seguridad.

        Args:
            user_id: ID del usuario autenticado (del JWT token)
            request: DTO con los datos a actualizar y password actual

        Returns:
            UpdateSecurityResponseDTO con el usuario actualizado

        Raises:
            UserNotFoundError: Si el usuario no existe
            InvalidCredentialsError: Si la contraseña actual es incorrecta
            DuplicateEmailError: Si el nuevo email ya está en uso
            ValueError: Si los datos no son válidos
        """
        async with self._uow:
            # Buscar usuario
            user_id_vo = UserId(user_id)
            user = await self._uow.users.find_by_id(user_id_vo)
            if not user:
                raise UserNotFoundError(f"User with id {user_id} not found")

            # Verificar contraseña actual
            if not user.verify_password(request.current_password):
                raise InvalidCredentialsError("Current password is incorrect")

            # Si se cambia el email, verificar que no esté en uso
            if request.new_email:
                email_vo = Email(request.new_email)
                existing_user = await self._uow.users.find_by_email(email_vo)
                if existing_user and str(existing_user.id.value) != user_id:
                    raise DuplicateEmailError(f"Email {request.new_email} is already in use")

                user.change_email(request.new_email)

            # Si se cambia el password
            if request.new_password:
                user.change_password(request.new_password)

            # Guardar cambios
            await self._uow.users.save(user)

            # Context manager hace commit automático y publica eventos

        # Construir respuesta
        return UpdateSecurityResponseDTO(
            user=UserResponseDTO.model_validate(user),
            message="Security settings updated successfully"
        )
