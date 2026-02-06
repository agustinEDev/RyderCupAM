"""Caso de Uso: Crear Ronda/Sesión de competición."""

from src.modules.competition.application.dto.round_match_dto import (
    CreateRoundRequestDTO,
    CreateRoundResponseDTO,
)
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.handicap_mode import HandicapMode
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotFoundError(Exception):
    """La competición no existe."""

    pass


class NotCompetitionCreatorError(Exception):
    """El usuario no es el creador de la competición."""

    pass


class CompetitionNotClosedError(Exception):
    """La competición no está en estado CLOSED."""

    pass


class GolfCourseNotInCompetitionError(Exception):
    """El campo de golf no está asociado a la competición."""

    pass


class DuplicateSessionError(Exception):
    """Ya existe una sesión con ese tipo en esa fecha."""

    pass


class DateOutOfRangeError(Exception):
    """La fecha está fuera del rango de la competición."""

    pass


class CreateRoundUseCase:
    """
    Caso de uso para crear una ronda/sesión de competición.

    Restricciones:
    - La competición debe estar en estado CLOSED
    - Solo el creador puede crear rondas
    - El campo de golf debe estar asociado a la competición
    - No pueden existir sesiones duplicadas (misma fecha + tipo)
    - La fecha debe estar dentro del rango de la competición
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, request: CreateRoundRequestDTO, user_id: UserId
    ) -> CreateRoundResponseDTO:
        async with self._uow:
            # 1. Buscar la competición
            competition_id = CompetitionId(request.competition_id)
            competition = await self._uow.competitions.find_by_id(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 2. Verificar creador
            if not competition.is_creator(user_id):
                raise NotCompetitionCreatorError(
                    "Solo el creador puede crear rondas"
                )

            # 3. Verificar estado CLOSED
            if not competition.status.value == "CLOSED":
                raise CompetitionNotClosedError(
                    f"La competición debe estar en estado CLOSED. "
                    f"Estado actual: {competition.status.value}"
                )

            # 4. Verificar campo de golf en la competición
            golf_course_id = GolfCourseId(request.golf_course_id)
            if not competition._has_golf_course(golf_course_id):
                raise GolfCourseNotInCompetitionError(
                    f"El campo de golf {request.golf_course_id} no está asociado "
                    f"a la competición"
                )

            # 5. Verificar fecha dentro del rango
            if not (competition.dates.start_date <= request.round_date <= competition.dates.end_date):
                raise DateOutOfRangeError(
                    f"La fecha {request.round_date} está fuera del rango "
                    f"({competition.dates.start_date} - {competition.dates.end_date})"
                )

            # 6. Verificar sesión duplicada
            existing_rounds = await self._uow.rounds.find_by_competition_and_date(
                competition_id, request.round_date
            )
            session_type = SessionType(request.session_type)
            for existing in existing_rounds:
                if existing.session_type == session_type:
                    raise DuplicateSessionError(
                        f"Ya existe una sesión {request.session_type} "
                        f"en la fecha {request.round_date}"
                    )

            # 7. Crear la ronda
            match_format = MatchFormat(request.match_format)
            handicap_mode = HandicapMode(request.handicap_mode) if request.handicap_mode else None

            round_entity = Round.create(
                competition_id=competition_id,
                golf_course_id=golf_course_id,
                round_date=request.round_date,
                session_type=session_type,
                match_format=match_format,
                handicap_mode=handicap_mode,
                allowance_percentage=request.allowance_percentage,
            )

            await self._uow.rounds.add(round_entity)

        return CreateRoundResponseDTO(
            id=round_entity.id.value,
            competition_id=round_entity.competition_id.value,
            status=round_entity.status.value,
            created_at=round_entity.created_at,
        )
