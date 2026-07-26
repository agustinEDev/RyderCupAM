"""Mapper para convertir entidades QuickMatch a DTOs de presentacion."""

from src.modules.quick_match.application.dto.quick_match_dto import (
    QuickMatchParticipantDTO,
    QuickMatchResponseDTO,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class QuickMatchDTOMapper:
    """Mapper para convertir entidades QuickMatch a DTOs de presentacion."""

    @staticmethod
    async def to_response_dto(
        quick_match: QuickMatch,
        user_uow: UserUnitOfWorkInterface,
        users_by_id: dict[UserId, User] | None = None,
    ) -> QuickMatchResponseDTO:
        """
        Convierte una QuickMatch a su DTO de respuesta.

        Si `users_by_id` se proporciona (precargado en bloque por el caller,
        p.ej. al listar varias partidas), se evita una query por participante.
        """
        if users_by_id is None:
            async with user_uow:
                users_by_id = {}
                for p in quick_match.participants:
                    user = await user_uow.users.find_by_id(p.user_id)
                    if user:
                        users_by_id[p.user_id] = user

        participants_dto = []
        for p in quick_match.participants:
            user = users_by_id.get(p.user_id)
            name = f"{user.first_name} {user.last_name}" if user else "Unknown"
            participants_dto.append(
                QuickMatchParticipantDTO(user_id=p.user_id.value, name=name, team=p.team)
            )

        return QuickMatchResponseDTO(
            id=quick_match.id.value,
            creator_id=quick_match.creator_id.value,
            golf_course_id=quick_match.golf_course_id.value,
            match_format=quick_match.match_format.value,
            status=quick_match.status.value,
            participants=participants_dto,
            created_at=quick_match.created_at,
            updated_at=quick_match.updated_at,
        )
