from typing import Optional

from src.modules.user.application.dto.user_dto import RegisterUserRequestDTO, UserResponseDTO
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import UserAlreadyExistsError
from src.modules.user.domain.services.user_finder import UserFinder
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)


class RegisterUserUseCase:
    """
    Caso de uso para registrar un nuevo usuario en el sistema.
    Orquesta la creación, validación y persistencia de un usuario.

    Opcionalmente, puede buscar el hándicap inicial del usuario
    si se proporciona un HandicapService.
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        handicap_service: Optional[HandicapService] = None
    ):
        self._uow = uow
        self._user_finder = UserFinder(self._uow.users)
        self._handicap_service = handicap_service

    async def execute(self, request: RegisterUserRequestDTO) -> UserResponseDTO:
        """
        Ejecuta el caso de uso.

        Args:
            request: DTO con la información para el registro.

        Returns:
            DTO con la información del usuario recién creado.

        Raises:
            UserAlreadyExistsError: Si el correo electrónico ya está en uso.
        """
        async with self._uow:
            # 1. Validar que el email no existe
            email_vo = Email(request.email)
            if await self._user_finder.by_email(email_vo):
                raise UserAlreadyExistsError(f"El email '{request.email}' ya está registrado.")

            # 2. Crear la entidad de dominio User
            new_user = User.create(
                email_str=request.email,
                plain_password=request.password,
                first_name=request.first_name,
                last_name=request.last_name,
            )

            # 2.5 Intentar buscar hándicap inicial (no bloquea el registro)
            handicap_value = None
            if self._handicap_service:
                try:
                    handicap_value = await self._handicap_service.search_handicap(
                        new_user.get_full_name()
                    )
                except Exception as e:
                    # No falla el registro si no se encuentra el hándicap
                    # TODO: Agregar logging apropiado
                    print(f"No se pudo obtener hándicap inicial: {e}")

            # 2.6 Si no se encontró en RFEG, usar hándicap manual si fue proporcionado
            if handicap_value is None and request.manual_handicap is not None:
                handicap_value = request.manual_handicap

            # 2.7 Actualizar hándicap si se obtuvo uno (de RFEG o manual)
            if handicap_value is not None:
                new_user.update_handicap(handicap_value)

            # 3. Guardar el usuario en el repositorio
            await self._uow.users.save(new_user)

            # 4. Confirmar la transacción
            await self._uow.commit()

            # 5. Devolver la respuesta como DTO
            return UserResponseDTO.model_validate(new_user)
