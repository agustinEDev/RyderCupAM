from src.modules.user.application.dto.user_dto import (
    FindUserRequestDTO,
    FindUserResponseDTO,
)
from src.modules.user.application.ports.bloqueos_interface import BloqueosInterface
from src.modules.user.domain.entities.user import User
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

    def __init__(self, uow: UserUnitOfWorkInterface, bloqueos: BloqueosInterface):
        """Con los usuarios y los bloqueos (obligatorios: quien me bloqueó no se encuentra)."""
        self._uow = uow
        self._user_finder = UserFinder(self._uow.users)
        # Quien me bloqueó no se encuentra (F-09, /code-review de la fase 3)
        self._bloqueos = bloqueos

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
        user = None
        email_vo = Email(request.email) if request.email else None

        # Buscar por email si se proporciona
        if email_vo:
            async with self._uow:
                user = self._solo_activa(await self._user_finder.by_email(email_vo))
            user = await self._sin_quien_me_bloqueo(user, viewer_id)

        # Si no se encontró por email, buscar por nombre completo
        if not user and request.full_name:
            async with self._uow:
                # Solo activas, ya en la consulta del repositorio (F7)
                user = await self._user_finder.by_full_name(request.full_name)
            user = await self._sin_quien_me_bloqueo(user, viewer_id)

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

    async def _sin_quien_me_bloqueo(self, user: User | None, viewer_id: UserId) -> User | None:
        """
        Quien me bloqueó no se encuentra: la misma respuesta que un correo o un
        nombre que no existen (F-09). A quien bloqueé yo, sí. Fuera de la unidad
        de trabajo de usuarios: la de los bloqueos comparte su sesión.
        """
        if user is None or user.id == viewer_id:
            return user
        return None if await self._bloqueos.me_bloqueo(viewer_id, user.id) else user

    @staticmethod
    def _solo_activa(user: User | None) -> User | None:
        """
        Una cuenta desactivada no se encuentra (F-01b): la misma respuesta que un
        correo o un nombre que no existen, sin su nombre ni su id.
        """
        return user if user is not None and user.is_active else None
