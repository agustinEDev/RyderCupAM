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
                        email=user.email.value,
                        full_name=user.get_full_name(),
                    )
                    for user in users
                ]
            )
