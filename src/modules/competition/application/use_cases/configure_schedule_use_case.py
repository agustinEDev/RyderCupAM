"""Caso de Uso: Configurar Schedule de la competición."""

from datetime import timedelta

from src.modules.competition.application.dto.round_match_dto import (
    ConfigureScheduleRequestDTO,
    ConfigureScheduleResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotClosedError,
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.schedule_format_service import ScheduleFormatService
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.schedule_config_mode import ScheduleConfigMode
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.user.domain.value_objects.user_id import UserId


class NoGolfCoursesError(Exception):
    """La competición no tiene campos de golf asociados."""

    pass


class ConfigureScheduleUseCase:
    """
    Caso de uso para configurar el schedule de la competición.

    AUTOMATIC: genera rondas según rotación de formato.
    - Sesiones se distribuyen: Fourball, Foursomes alternando, Singles siempre última
    - Se rotan campos de golf por display_order
    - Sesiones por día configurables (1-3, default 2)

    MANUAL: solo retorna ack (rondas se crean individualmente con CreateRoundUseCase).

    Elimina rondas existentes antes de re-configurar (AUTO).
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        schedule_format_service: ScheduleFormatService | None = None,
    ):
        self._uow = uow
        self._format_service = schedule_format_service or ScheduleFormatService()

    async def execute(
        self, request: ConfigureScheduleRequestDTO, user_id: UserId
    ) -> ConfigureScheduleResponseDTO:
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
                raise NotCompetitionCreatorError("Solo el creador puede configurar el schedule")

            # 3. Verificar estado CLOSED
            if competition.status != CompetitionStatus.CLOSED:
                raise CompetitionNotClosedError(
                    f"La competición debe estar en CLOSED. Estado: {competition.status.value}"
                )

            # MANUAL mode: solo ack
            if request.mode == ScheduleConfigMode.MANUAL:
                return ConfigureScheduleResponseDTO(
                    competition_id=request.competition_id,
                    mode=ScheduleConfigMode.MANUAL.value,
                    rounds_created=0,
                    message="Modo MANUAL configurado. Cree rondas individualmente.",
                )

            # AUTOMATIC mode
            # 4. Verificar campos de golf
            golf_courses = competition.golf_courses
            if not golf_courses:
                raise NoGolfCoursesError("La competición no tiene campos de golf asociados")

            # 5. Eliminar rondas existentes
            existing_rounds = await self._uow.rounds.find_by_competition(competition_id)
            for r in existing_rounds:
                # Eliminar partidos de la ronda
                matches = await self._uow.matches.find_by_round(r.id)
                for m in matches:
                    await self._uow.matches.delete(m.id)
                await self._uow.rounds.delete(r.id)

            if existing_rounds:
                await self._uow.flush()  # Forzar DELETE antes de INSERT (unique constraint)

            # 6. Generar rondas automáticamente
            total_sessions = request.total_sessions or 3
            sessions_per_day = request.sessions_per_day or 2
            session_types = [SessionType.MORNING, SessionType.AFTERNOON, SessionType.EVENING]

            # Generar secuencia de formatos via domain service
            session_formats = self._format_service.build_format_sequence(total_sessions)

            current_date = competition.dates.start_date
            rounds_created = 0
            session_in_day = 0

            for i in range(total_sessions):
                # Parar si pasamos del end_date
                if current_date > competition.dates.end_date:
                    break

                match_format = session_formats[i]

                # Seleccionar campo de golf (rotación por display_order)
                gc = golf_courses[i % len(golf_courses)]

                # Seleccionar tipo de sesión
                session_type = session_types[session_in_day]

                round_entity = Round.create(
                    competition_id=competition_id,
                    golf_course_id=gc.golf_course_id,
                    round_date=current_date,
                    session_type=session_type,
                    match_format=match_format,
                )
                await self._uow.rounds.add(round_entity)
                rounds_created += 1

                # Avanzar sesión/día
                session_in_day += 1
                if session_in_day >= sessions_per_day:
                    session_in_day = 0
                    current_date += timedelta(days=1)

        return ConfigureScheduleResponseDTO(
            competition_id=request.competition_id,
            mode=ScheduleConfigMode.AUTOMATIC.value,
            rounds_created=rounds_created,
            message=f"Schedule generado con {rounds_created} rondas.",
        )

