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
        Los invitados (`is_guest=True`) no tienen `user_id` y se resuelven
        directamente desde sus datos manuales, sin tocar `users_by_id`.
        """
        if users_by_id is None:
            registered_ids = [p.user_id for p in quick_match.participants if p.user_id is not None]
            async with user_uow:
                users_by_id = {}
                for user_id in registered_ids:
                    user = await user_uow.users.find_by_id(user_id)
                    if user:
                        users_by_id[user_id] = user

        participants_dto = []
        for p in quick_match.participants:
            if p.is_guest:
                name = f"{p.first_name} {p.last_name}"
                handicap = p.handicap
            else:
                user = users_by_id.get(p.user_id)
                name = f"{user.first_name} {user.last_name}" if user else "Unknown"
                handicap = user.handicap.value if user and user.handicap else None
            participants_dto.append(
                QuickMatchParticipantDTO(
                    participant_id=p.participant_id.value,
                    user_id=p.user_id.value if p.user_id else None,
                    name=name,
                    handicap=handicap,
                    team=p.team,
                    is_guest=p.is_guest,
                    tee_category=p.tee_category.value if p.tee_category else None,
                    tee_gender=p.tee_gender.value if p.tee_gender else None,
                )
            )

        return QuickMatchResponseDTO(
            id=quick_match.id.value,
            creator_id=quick_match.creator_id.value,
            golf_course_id=quick_match.golf_course_id.value,
            match_format=quick_match.match_format.value if quick_match.match_format else None,
            scoring_format=(
                quick_match.scoring_format.value if quick_match.scoring_format else None
            ),
            status=quick_match.status.value,
            name=quick_match.name,
            allowance_percentage=quick_match.allowance_percentage,
            effective_allowance=quick_match.get_effective_allowance(),
            participants=participants_dto,
            scorer_ids=[sid.value for sid in quick_match.scorer_ids],
            created_at=quick_match.created_at,
            updated_at=quick_match.updated_at,
        )
