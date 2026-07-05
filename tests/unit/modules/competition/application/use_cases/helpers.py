"""Helper factories para tests de use cases de Enrollment/Handicap."""

from datetime import date
from decimal import Decimal

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId


async def create_competition(uow: InMemoryUnitOfWork, creator_id: UserId):
    """Crea una competición en DRAFT."""
    create_uc = CreateCompetitionUseCase(uow)
    request = CreateCompetitionRequestDTO(
        name="Test Cup",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 3),
        main_country="ES",
        play_mode="SCRATCH",
        max_players=24,
    )
    return await create_uc.execute(request, creator_id)


async def set_competition_status(uow: InMemoryUnitOfWork, competition_id, status: str):
    """Mueve una competición a través de sus transiciones hasta `status`."""
    async with uow:
        competition = await uow.competitions.find_by_id(CompetitionId(competition_id))
        if status in ("ACTIVE", "CLOSED", "IN_PROGRESS", "COMPLETED", "CANCELLED"):
            competition.activate()
        if status in ("CLOSED", "IN_PROGRESS", "COMPLETED"):
            competition.close_enrollments()
        if status in ("IN_PROGRESS", "COMPLETED"):
            competition.start()
        if status == "COMPLETED":
            competition.complete()
        if status == "CANCELLED":
            competition.cancel()
        await uow.competitions.update(competition)
        await uow.commit()


async def create_approved_enrollment(
    uow: InMemoryUnitOfWork,
    competition_id,
    user_id: UserId,
    custom_handicap: Decimal | None = None,
) -> Enrollment:
    """Crea un enrollment ya aprobado, opcionalmente con hándicap personalizado."""
    enrollment = Enrollment.direct_enroll(
        id=EnrollmentId.generate(),
        competition_id=CompetitionId(competition_id),
        user_id=user_id,
        custom_handicap=custom_handicap,
    )
    async with uow:
        await uow.enrollments.add(enrollment)
        await uow.commit()
    return enrollment
