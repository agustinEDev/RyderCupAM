"""Caso de Uso: Actualizar Ronda/Sesión de competición."""

from datetime import UTC, datetime

from src.modules.competition.application.dto.round_match_dto import (
    UpdateRoundRequestDTO,
    UpdateRoundResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    DateOutOfRangeError,
    FranjaInvalidaError,
    NotCompetitionCreatorError,
    RoundNotFoundError,
    RoundNotModifiableError,
)
from src.modules.competition.application.services.esperas_de_la_competicion import (
    EsperasDeLaCompeticion,
)
from src.modules.competition.application.services.franjas import (
    comprobar_agenda,
    comprobar_que_nadie_pierde_su_sitio,
    comprobar_solape,
    comprobar_tipo,
    hoja_de,
)
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.application.services.partidas_de_la_franja import (
    comprobar_que_caben_las_partidas,
    recalcular_partidas,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.handicap_mode import HandicapMode
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat


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

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        jugadores: JugadoresDeLaPartida | None = None,
    ):
        """
        Args:
            jugadores: Para rehacer las fotos de las partidas si una franja cambia
                de campo (#251). Sin él, ese cambio con partidas se rechaza
        """
        self._uow = uow
        self._jugadores = jugadores

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
            # que se protege es la sesión ya jugada, y eso lo mira la sesión. Las
            # franjas de un stroke play, hasta iniciar (#251)
            comprobar_agenda(competition)

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

            # Las sesiones del día de destino, una sola vez: para el duplicado y
            # para el solape de una franja (#251)
            dia = request.round_date or round_entity.round_date
            del_dia = await self._uow.rounds.find_by_competition_and_date(
                round_entity.competition_id, dia
            )
            if request.session_type or request.round_date:
                check_date = dia
                check_session = (
                    SessionType(request.session_type)
                    if request.session_type
                    else round_entity.session_type
                )
                existing_rounds = del_dia
                for existing in existing_rounds:
                    if existing.id != round_entity.id and existing.session_type == check_session:
                        raise DuplicateSessionError(
                            f"Ya existe una sesión {check_session.value} en la fecha {check_date}"
                        )

            # 6b. Una franja solo cambia su hoja (no tiene formato), y no puede
            #     acabar solapada con otra de su jornada (#251)
            hoja = self._comprobar_franja(request, competition, round_entity, del_dia)
            # Y que nadie de dentro pierda su sitio (#251)
            await comprobar_que_nadie_pierde_su_sitio(
                self._uow, round_entity, hoja, request.round_date
            )
            # Y que sus partidas quepan en la hoja nueva (D9, #251)
            partidas = await self._partidas_que_caben(round_entity, hoja)
            campo_anterior = round_entity.golf_course_id

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
                if hoja is not None:
                    round_entity.cambiar_hoja_de_salidas(hoja)
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

            await self._recalcular_partidas(competition, round_entity, partidas, campo_anterior)

            await self._uow.rounds.update(round_entity)
            # Si la franja creció, sus nuevas plazas para los que esperan (#251); si
            # no hay sitio libre o no es una franja, no hace nada
            await self._listas_al_dia(competition, round_entity, request)

        return UpdateRoundResponseDTO(
            id=round_entity.id.value,
            status=round_entity.status.value,
            updated_at=round_entity.updated_at,
        )

    async def _partidas_que_caben(self, franja: Round, hoja: HojaDeSalidas | None) -> list[Partida]:
        """Las partidas de la franja, si caben en la hoja nueva (D9, #251)."""
        partidas = await self._uow.partidas.de_la_franja(franja.id)
        if hoja is not None:
            comprobar_que_caben_las_partidas(partidas, hoja)
        return partidas

    async def _recalcular_partidas(
        self,
        competition: Competition,
        franja: Round,
        partidas: list[Partida],
        campo_anterior: GolfCourseId,
    ) -> None:
        """
        Otro campo: otras barras y otros golpes en las partidas sin salir. Si alguien
        no tiene barras en el nuevo, se rechaza con la lista (D9, G2, #251).
        """
        if not partidas or franja.golf_course_id == campo_anterior:
            return
        if self._jugadores is None:
            raise FranjaInvalidaError(
                "No se puede cambiar el campo de una franja con partidas aquí."
            )
        await recalcular_partidas(self._uow, self._jugadores, competition, franja, partidas)

    @staticmethod
    def _comprobar_franja(
        request: UpdateRoundRequestDTO,
        competition: Competition,
        round_entity: Round,
        del_dia: list[Round],
    ) -> HojaDeSalidas | None:
        """
        La hoja nueva, si viene; y que la sesión sigue siendo de su tipo y no choca
        con otra franja de su jornada y su campo (se cambie la hoja, el día o el campo).
        """
        hoja = hoja_de(request.tee_sheet)
        comprobar_tipo(
            competition,
            hoja,
            con_formato=request.match_format is not None
            or request.handicap_mode is not None
            or request.allowance_percentage is not None
            or request.clear_allowance,
            trae_formato=request.match_format is not None,
            exige_formato=False,
        )
        hoja_final = hoja or round_entity.hoja_de_salidas
        if hoja_final is not None and (
            hoja is not None or request.round_date or request.golf_course_id
        ):
            comprobar_solape(
                hoja_final,
                request.round_date or round_entity.round_date,
                GolfCourseId(request.golf_course_id)
                if request.golf_course_id
                else round_entity.golf_course_id,
                del_dia,
                excepto=round_entity.id,
            )
        return hoja

    async def _listas_al_dia(
        self, competition: Competition, round_entity: Round, request: UpdateRoundRequestDTO
    ) -> None:
        """
        Las plazas que haya ahora libres, para los que esperan (#251); y si la
        franja cambió de día, cambia qué días juega cada uno: listas al día.
        """
        esperas = EsperasDeLaCompeticion(self._uow)
        if request.tee_sheet is not None:
            await esperas.rellenar(competition, round_entity.id, datetime.now(UTC))
        if request.round_date:
            await esperas.limpiar(competition)
