"""Caso de Uso: Configurar Schedule de la competición."""

from datetime import timedelta

from src.modules.competition.application.dto.round_match_dto import (
    ConfigureScheduleRequestDTO,
    ConfigureScheduleResponseDTO,
)
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotFoundError(Exception):
    """La competición no existe."""

    pass


class NotCompetitionCreatorError(Exception):
    """El usuario no es el creador."""

    pass


class CompetitionNotClosedError(Exception):
    """La competición no está en estado CLOSED."""

    pass


class NoGolfCoursesError(Exception):
    """La competición no tiene campos de golf asociados."""

    pass


class ConfigureScheduleUseCase:
    """
    Caso de uso para configurar el schedule de la competición.

    AUTOMATIC: genera rondas según rotación de formato.
    - Sesiones se distribuyen: Foursomes, Fourball, Singles (última siempre Singles)
    - Se rotan campos de golf por display_order
    - Sesiones por día configurables (1-3, default 2)

    MANUAL: solo retorna ack (rondas se crean individualmente con CreateRoundUseCase).

    Elimina rondas existentes antes de re-configurar (AUTO).
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

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
                raise NotCompetitionCreatorError(
                    "Solo el creador puede configurar el schedule"
                )

            # 3. Verificar estado CLOSED
            if not competition.status.value == "CLOSED":
                raise CompetitionNotClosedError(
                    f"La competición debe estar en CLOSED. Estado: {competition.status.value}"
                )

            # MANUAL mode: solo ack
            if request.mode == "MANUAL":
                return ConfigureScheduleResponseDTO(
                    competition_id=request.competition_id,
                    mode="MANUAL",
                    rounds_created=0,
                    message="Modo MANUAL configurado. Cree rondas individualmente.",
                )

            # AUTOMATIC mode
            # 4. Verificar campos de golf
            golf_courses = competition.golf_courses
            if not golf_courses:
                raise NoGolfCoursesError(
                    "La competición no tiene campos de golf asociados"
                )

            # 5. Eliminar rondas existentes
            existing_rounds = await self._uow.rounds.find_by_competition(competition_id)
            for r in existing_rounds:
                # Eliminar partidos de la ronda
                matches = await self._uow.matches.find_by_round(r.id)
                for m in matches:
                    await self._uow.matches.delete(m.id)
                await self._uow.rounds.delete(r.id)

            # 6. Generar rondas automáticamente
            total_sessions = request.total_sessions or 3
            sessions_per_day = request.sessions_per_day or 2
            session_types = [SessionType.MORNING, SessionType.AFTERNOON, SessionType.EVENING]

            # Rotación de formatos: Foursomes, Fourball, ..., Singles al final
            format_rotation = [MatchFormat.FOURSOMES, MatchFormat.FOURBALL, MatchFormat.SINGLES]

            current_date = competition.dates.start_date
            rounds_created = 0
            session_in_day = 0

            for i in range(total_sessions):
                # Seleccionar formato según rotación
                if i == total_sessions - 1:
                    # Última sesión siempre Singles
                    match_format = MatchFormat.SINGLES
                else:
                    match_format = format_rotation[i % len(format_rotation)]

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
                    # No pasar del end_date
                    current_date = min(current_date, competition.dates.end_date)

        return ConfigureScheduleResponseDTO(
            competition_id=request.competition_id,
            mode="AUTOMATIC",
            rounds_created=rounds_created,
            message=f"Schedule generado con {rounds_created} rondas.",
        )
