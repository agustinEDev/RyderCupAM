from src.modules.user.application.dto.user_dto import (
    SearchUsersItemDTO,
    SearchUsersResponseDTO,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)


class SearchUsersUseCase:
    """
    Use case for autocomplete user search by partial name.
    Returns a list of users matching the query.

    Devuelve **solo lo publico**: nombre, apellidos y foto. Cualquier usuario
    registrado puede buscar por nombre, asi que todo lo que salga de aqui es
    visible para cualquiera. El correo se retiro por eso: tecleando nombres
    sueltos se podian recolectar direcciones de gente con la que no tienes
    ninguna relacion.
    """

    MIN_QUERY_LENGTH = 2
    MAX_RESULTS = 10

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, query: str) -> SearchUsersResponseDTO:
        if not query or len(query.strip()) < self.MIN_QUERY_LENGTH:
            return SearchUsersResponseDTO(users=[])

        async with self._uow:
            users = await self._uow.users.search_by_partial_name(
                query.strip(), limit=self.MAX_RESULTS
            )

            return SearchUsersResponseDTO(
                users=[
                    SearchUsersItemDTO(
                        user_id=user.id.value,
                        full_name=user.get_full_name(),
                        first_name=user.first_name,
                        last_name=user.last_name,
                        avatar_source=user.avatar_source.value,
                        avatar_preset_id=user.avatar_preset_id,
                        has_avatar_upload=user.active_avatar_upload_id is not None,
                    )
                    for user in users
                ]
            )
