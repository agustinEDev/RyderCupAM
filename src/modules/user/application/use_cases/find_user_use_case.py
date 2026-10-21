from src.modules.user.application.dto.user_dto import (
    FindUserRequestDTO,
    FindUserResponseDTO,
)
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.user_finder import UserFinder
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.user_id import UserId


class FindUserUseCase:
    """
    Caso de uso para buscar usuarios por email o nombre completo.

    Este caso de uso permite encontrar usuarios utilizando diferentes criterios
    de búsqueda y devuelve información básica del usuario encontrado.
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow
        self._user_finder = UserFinder(self._uow.users)

    async def execute(
        self, request: FindUserRequestDTO, *, viewer_id: UserId
    ) -> FindUserResponseDTO:
        """
        Ejecuta el caso de uso de búsqueda.

        El correo del encontrado solo vuelve si es eco del que se tecleó o si
        es quien busca; si no, vacío: buscar por nombre no destapa correos.

        Args:
            request: DTO con los criterios de búsqueda.
            viewer_id: Quien busca.

        Returns:
            DTO con la información básica del usuario encontrado.

        Raises:
            UserNotFoundError: Si no se encuentra ningún usuario con los criterios dados.
        """
        async with self._uow:
            user = None
            email_vo = Email(request.email) if request.email else None

            # Buscar por email si se proporciona
            if email_vo:
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

            # Eco de lo tecleado, o uno mismo
            ve_correo = user.email == email_vo or user.id == viewer_id
            return FindUserResponseDTO(
                user_id=user.id.value,
                email=user.email.value if ve_correo else "",
                full_name=user.get_full_name(),
                display_name=user.display_name,
            )
