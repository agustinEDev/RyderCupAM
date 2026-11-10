from src.modules.user.application.dto.user_dto import (
    SearchUsersItemDTO,
    SearchUsersRequestDTO,
    SearchUsersResponseDTO,
)
from src.modules.user.application.ports.bloqueos_interface import BloqueosInterface
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SearchUsersUseCase:
    """
    Use case for autocomplete user search by partial name.
    Returns a list of users matching the query.

    Devuelve **solo lo publico**: nombre, apellidos, alias y foto. Cualquier
    usuario registrado puede buscar por nombre, asi que todo lo que salga de
    aqui es visible para cualquiera. El correo se retiro por eso: tecleando
    nombres sueltos se podian recolectar direcciones de gente con la que no
    tienes ninguna relacion. El alias no amplia esa exposicion: es publico por
    diseño, porque es lo que otra gente teclea para encontrarte.
    """

    MIN_QUERY_LENGTH = 2
    MAX_RESULTS = 10

    def __init__(self, uow: UserUnitOfWorkInterface, bloqueos: BloqueosInterface):
        """Con los usuarios y los bloqueos: quien me bloqueó no sale al buscar."""
        self._uow = uow
        self._bloqueos = bloqueos

    async def execute(self, request: SearchUsersRequestDTO) -> SearchUsersResponseDTO:
        """Quien busca (`viewer_id`) no sale en sus resultados (FE #938)."""
        query = request.query
        if not query or len(query.strip()) < self.MIN_QUERY_LENGTH:
            return SearchUsersResponseDTO(users=[])

        quien = UserId(request.viewer_id)
        # Quien me bloqueó no existe para mí (F-09): fuera en la propia consulta,
        # sin ocupar huecos del límite. A quien bloqueé yo, sí lo encuentro
        me_bloquearon = await self._bloqueos.quienes_me_bloquearon(quien)
        async with self._uow:
            users = await self._uow.users.search_by_partial_name(
                query.strip(),
                limit=self.MAX_RESULTS,
                exclude_user_id=quien,
                exclude_user_ids=me_bloquearon,
            )

            return SearchUsersResponseDTO(
                users=[
                    SearchUsersItemDTO(
                        user_id=user.id.value,
                        full_name=user.get_full_name(),
                        first_name=user.first_name,
                        last_name=user.last_name,
                        alias=user.alias,
                        display_name=user.display_name,
                        avatar_source=user.avatar_source.value,
                        avatar_preset_id=user.avatar_preset_id,
                        has_avatar_upload=user.active_avatar_upload_id is not None,
                    )
                    for user in users
                ]
            )
