"""
Update Profile Use Case - Application Layer

Caso de uso para actualizar la información personal de un usuario (nombre y apellidos).
NO requiere validación de contraseña, solo autenticación JWT.
"""

from sqlalchemy.exc import IntegrityError

from src.modules.user.application.dto.user_dto import (
    UpdateProfileRequestDTO,
    UpdateProfileResponseDTO,
    UserResponseDTO,
)
from src.modules.user.domain.errors.user_errors import (
    AliasAlreadyTakenError,
    UserNotFoundError,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.domain.value_objects.country_code import CountryCode


class UpdateProfileUseCase:
    """
    Caso de uso: Actualizar información personal del usuario.

    Permite a un usuario autenticado actualizar su nombre y/o apellidos
    sin necesidad de proporcionar su contraseña actual.
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        country_repository: CountryRepositoryInterface,
    ):
        """
        Inicializa el caso de uso con sus dependencias.

        Args:
            uow: Unit of Work para manejar transacciones
            country_repository: Repositorio de países para validar country_code
        """
        self._uow = uow
        self._country_repository = country_repository

    async def execute(
        self, user_id: str, request: UpdateProfileRequestDTO
    ) -> UpdateProfileResponseDTO:
        """
        Ejecuta el caso de uso de actualización de perfil.

        Args:
            user_id: ID del usuario autenticado (del JWT token)
            request: DTO con los datos a actualizar

        Returns:
            UpdateProfileResponseDTO con el usuario actualizado

        Raises:
            UserNotFoundError: Si el usuario no existe
            AliasAlreadyTakenError: Si el alias pedido ya lo tiene otra persona
            ValueError: Si los datos no son válidos
        """
        try:
            async with self._uow:
                # Buscar usuario
                user_id_vo = UserId(user_id)
                user = await self._uow.users.find_by_id(user_id_vo)
                if not user:
                    raise UserNotFoundError(f"User with id {user_id} not found")

                # Validar que el country_code existe (si se proporcionó)
                if request.country_code:
                    country_code_vo = CountryCode(request.country_code)
                    country_exists = await self._country_repository.exists(country_code_vo)
                    if not country_exists:
                        raise ValueError(
                            f"El código de país '{request.country_code}' no es válido."
                        )

                # Alias libre. La cadena vacía es "quítamelo", y ahí no hay nada
                # que comprobar. Que el alias siga siendo el suyo tampoco es
                # conflicto: cambiar solo las mayúsculas debe poder hacerse
                if request.alias:
                    owner = await self._uow.users.find_by_alias(request.alias)
                    if owner and owner.id != user.id:
                        raise AliasAlreadyTakenError(
                            f"El alias '{request.alias}' ya está en uso."
                        )

                # Actualizar perfil (entity valida y emite eventos)
                user.update_profile(
                    first_name=request.first_name,
                    last_name=request.last_name,
                    country_code_str=request.country_code,
                    gender=request.gender,
                    alias=request.alias,
                )

                # Guardar cambios
                await self._uow.users.save(user)

                # Context manager hace commit automático y publica eventos
        except IntegrityError as e:
            # La comprobación de arriba no basta: entre ella y el commit cabe
            # otra petición pidiendo el mismo alias, y quien lo resuelve de
            # verdad es el índice único. Solo se traduce SU violación;
            # cualquier otra se deja subir como está
            if "ix_users_alias_lower" in str(e.orig):
                raise AliasAlreadyTakenError(
                    f"El alias '{request.alias}' ya está en uso."
                ) from e
            raise

        # Construir respuesta
        return UpdateProfileResponseDTO(
            user=UserResponseDTO.model_validate(user),
            message="Profile updated successfully",
        )
