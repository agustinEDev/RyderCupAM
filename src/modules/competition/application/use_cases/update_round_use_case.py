"""Caso de Uso: Actualizar Ronda/Sesión de competición."""

from src.modules.competition.application.dto.round_match_dto import (
    UpdateRoundRequestDTO,
    UpdateRoundResponseDTO,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.handicap_mode import HandicapMode
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId


class RoundNotFoundError(Exception):
    """La ronda no existe."""

    pass


class NotCompetitionCreatorError(Exception):
    """El usuario no es el creador de la competición."""

    pass


class RoundNotModifiableError(Exception):
    """La ronda no puede modificarse en su estado actual."""

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


class UpdateRoundUseCase:
    """
    Caso de uso para actualizar una ronda de competición.

    Restricciones:
    - La ronda debe existir
    - Solo el creador puede actualizar
    - La competición debe estar en estado CLOSED
    - La ronda debe estar en estado modificable (PENDING_TEAMS/PENDING_MATCHES)
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, request: UpdateRoundRequestDTO, user_id: UserId
    ) -> UpdateRoundResponseDTO:
        async with self._uow:
            # 1. Buscar la ronda
            round_id = RoundId(request.round_id)
            round_entity = await self._uow.rounds.find_by_id(round_id)

            if not round_entity:
                raise RoundNotFoundError(
                    f"No existe ronda con ID {request.round_id}"
                )

            # 2. Buscar la competición
            competition = await self._uow.competitions.find_by_id(
                round_entity.competition_id
            )

            if not competition:
                raise RoundNotFoundError("La competición asociada no existe")

            # 3. Verificar creador
            if not competition.is_creator(user_id):
                raise NotCompetitionCreatorError(
                    "Solo el creador puede actualizar rondas"
                )

            # 4. Verificar competición CLOSED
            if competition.status != CompetitionStatus.CLOSED:
                raise CompetitionNotClosedError(
                    f"La competición debe estar en estado CLOSED. "
                    f"Estado actual: {competition.status.value}"
                )

            # 5. Verificar campo de golf si se cambia
            golf_course_id = None
            if request.golf_course_id:
                golf_course_id = GolfCourseId(request.golf_course_id)
                if not competition.has_golf_course(golf_course_id):
                    raise GolfCourseNotInCompetitionError(
                        f"El campo de golf {request.golf_course_id} no está "
                        f"asociado a la competición"
                    )

            # 6. Verificar sesión duplicada si se cambia fecha o tipo
            if request.session_type or request.round_date:
                check_date = request.round_date or round_entity.round_date
                check_session = (
                    SessionType(request.session_type)
                    if request.session_type
                    else round_entity.session_type
                )
                existing_rounds = await self._uow.rounds.find_by_competition_and_date(
                    round_entity.competition_id, check_date
                )
                for existing in existing_rounds:
                    if existing.id != round_entity.id and existing.session_type == check_session:
                        raise DuplicateSessionError(
                            f"Ya existe una sesión {check_session.value} "
                            f"en la fecha {check_date}"
                        )

            # 7. Actualizar la ronda (validación de estado dentro del dominio)
            session_type = SessionType(request.session_type) if request.session_type else None
            match_format = MatchFormat(request.match_format) if request.match_format else None
            handicap_mode = HandicapMode(request.handicap_mode) if request.handicap_mode else None

            try:
                round_entity.update_details(
                    round_date=request.round_date,
                    session_type=session_type,
                    golf_course_id=golf_course_id,
                    match_format=match_format,
                    handicap_mode=handicap_mode,
                    allowance_percentage=request.allowance_percentage,
                    clear_allowance=request.clear_allowance,
                )
            except ValueError as e:
                raise RoundNotModifiableError(str(e)) from e

            await self._uow.rounds.update(round_entity)

        return UpdateRoundResponseDTO(
            id=round_entity.id.value,
            status=round_entity.status.value,
            updated_at=round_entity.updated_at,
        )
