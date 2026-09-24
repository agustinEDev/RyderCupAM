"""Caso de Uso: Actualizar Ronda/Sesión de competición."""

from src.modules.competition.application.dto.round_match_dto import (
    UpdateRoundRequestDTO,
    UpdateRoundResponseDTO,
)
from src.modules.competition.application.exceptions import (
    AgendaNotEditableError,
    CompetitionNotFoundError,
    DateOutOfRangeError,
    NotCompetitionCreatorError,
    RoundNotFoundError,
    RoundNotModifiableError,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.handicap_mode import HandicapMode
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId


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
    - La competición no puede haber terminado ni estar cancelada (BE #365)
    - La ronda debe estar en estado modificable (PENDING_TEAMS/PENDING_MATCHES)
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, request: UpdateRoundRequestDTO, user_id: UserId, is_admin: bool = False
    ) -> UpdateRoundResponseDTO:
        async with self._uow:
            # 1. Buscar la ronda
            round_id = RoundId(request.round_id)
            round_entity = await self._uow.rounds.find_by_id(round_id)

            if not round_entity:
                raise RoundNotFoundError(f"No existe ronda con ID {request.round_id}")

            # 2. Buscar la competición
            # Con la fila bloqueada: cambiar el formato tira los sobres de la
            # sesion (FE #655), y hacerlo mientras un capitan entrega el suyo
            # dejaria uno del formato viejo dentro
            competition = await self._uow.competitions.find_by_id_for_update(
                round_entity.competition_id
            )

            if not competition:
                raise CompetitionNotFoundError("La competición asociada no existe")

            # Releída tras el bloqueo: si mientras se esperaba otra petición
            # generó sus partidos, se decide con eso y no con lo de antes
            round_entity = await self._uow.rounds.find_by_id_for_update(round_id) or round_entity

            # 3. Verificar creador
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede actualizar rondas")

            # La agenda se edita desde que la competición existe (BE #365): lo
            # que se protege es la sesión ya jugada, y eso lo mira la sesión
            if not competition.status.allows_agenda_edits():
                raise AgendaNotEditableError(
                    "La agenda solo se puede cambiar hasta que la competición termina o se cancela. "
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
            # Dentro del torneo, como al crearla: con la agenda abierta desde el
            # principio, mover una sesión fuera de las fechas ya no esperaba al
            # cierre para ser posible (BE #365, CodeRabbit)
            if request.round_date and not (
                competition.dates.start_date <= request.round_date <= competition.dates.end_date
            ):
                raise DateOutOfRangeError(
                    f"La fecha {request.round_date} está fuera del rango "
                    f"({competition.dates.start_date} - {competition.dates.end_date})"
                )

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
                            f"Ya existe una sesión {check_session.value} en la fecha {check_date}"
                        )

            # 7. Actualizar la ronda (validación de estado dentro del dominio)
            session_type = SessionType(request.session_type) if request.session_type else None
            match_format = MatchFormat(request.match_format) if request.match_format else None
            handicap_mode = HandicapMode(request.handicap_mode) if request.handicap_mode else None

            formato_anterior = round_entity.match_format
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

            if formato_anterior is not None and formato_anterior != round_entity.match_format:
                # Los sobres eran de otro formato: uno de parejas no vale para
                # unos individuales —el capitan ya no podria ni corregirlo— y al
                # reves revienta al generar los partidos. Se tiran, y los
                # capitanes vuelven a entregar (FE #655)
                await self._uow.envelopes.delete_by_round(round_entity.id)
                # Y el motivo por el que no salieron los partidos era de ESOS
                # sobres: si se queda, «Generar» se ofrece como reintento y, sin
                # sobres, empareja por handicap (revision de la FE #711)
                round_entity.clear_match_generation_block()

            await self._uow.rounds.update(round_entity)

        return UpdateRoundResponseDTO(
            id=round_entity.id.value,
            status=round_entity.status.value,
            updated_at=round_entity.updated_at,
        )
