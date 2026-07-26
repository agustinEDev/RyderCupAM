"""Mapper para convertir entidades QuickMatch a DTOs de presentacion."""

from src.modules.quick_match.application.dto.quick_match_dto import (
    QuickMatchParticipantDTO,
    QuickMatchResponseDTO,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)


class QuickMatchDTOMapper:
    """Mapper para convertir entidades QuickMatch a DTOs de presentacion."""

    @staticmethod
    async def to_response_dto(
        quick_match: QuickMatch, user_uow: UserUnitOfWorkInterface
    ) -> QuickMatchResponseDTO:
        async with user_uow:
            participants_dto = []
            for p in quick_match.participants:
                if p.is_guest:
                    name = f"{p.first_name} {p.last_name}"
                    handicap = p.handicap
                else:
                    user = await user_uow.users.find_by_id(p.user_id)
                    name = f"{user.first_name} {user.last_name}" if user else "Unknown"
                    handicap = None
                participants_dto.append(
                    QuickMatchParticipantDTO(
                        participant_id=p.participant_id.value,
                        user_id=p.user_id.value if p.user_id else None,
                        name=name,
                        handicap=handicap,
                        team=p.team,
                        is_guest=p.is_guest,
                    )
                )

        return QuickMatchResponseDTO(
            id=quick_match.id.value,
            creator_id=quick_match.creator_id.value,
            golf_course_id=quick_match.golf_course_id.value,
            match_format=quick_match.match_format.value,
            status=quick_match.status.value,
            participants=participants_dto,
            scorer_ids=[sid.value for sid in quick_match.scorer_ids],
            created_at=quick_match.created_at,
            updated_at=quick_match.updated_at,
        )
