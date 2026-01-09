from src.modules.user.application.dto.user_dto import FindUserRequestDTO, FindUserResponseDTO
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.user_finder import UserFinder
from src.modules.user.domain.value_objects.email import Email


class FindUserUseCase:
    """
    Caso de uso para buscar usuarios por email o nombre completo.

    Este caso de uso permite encontrar usuarios utilizando diferentes criterios
    de búsqueda y devuelve información básica del usuario encontrado.
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow
        self._user_finder = UserFinder(self._uow.users)

    async def execute(self, request: FindUserRequestDTO) -> FindUserResponseDTO:
        """
        Ejecuta el caso de uso de búsqueda.

        Args:
            request: DTO con los criterios de búsqueda.

        Returns:
            DTO con la información básica del usuario encontrado.

        Raises:
            UserNotFoundError: Si no se encuentra ningún usuario con los criterios dados.
        """
        async with self._uow:
            user = None

            # Buscar por email si se proporciona
            if request.email:
                email_vo = Email(request.email)
                user = await self._user_finder.by_email(email_vo)

            # Si no se encontró por email, buscar por nombre completo
            if not user and request.full_name:
                user = await self._user_finder.by_full_name(request.full_name)

            # Si no se encuentra el usuario, lanzar excepción
            if not user:
                search_criteria = []
                if request.email:
                    search_criteria.append(f"email '{request.email}'")
                if request.full_name:
                    search_criteria.append(f"nombre completo '{request.full_name}'")

                criteria_str = " o ".join(search_criteria)
                raise UserNotFoundError(f"No se encontró ningún usuario con {criteria_str}.")

            # Crear y devolver el DTO de respuesta
            return FindUserResponseDTO(
                user_id=user.id.value, email=user.email.value, full_name=user.get_full_name()
            )
