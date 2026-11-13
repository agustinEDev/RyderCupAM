"""Caso de Uso: Generar partidos para una ronda."""

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

from src.modules.competition.application.dto.round_match_dto import (
    GenerateMatchesRequestDTO,
    GenerateMatchesResponseDTO,
    ManualPairingDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotClosedError,
    CompetitionNotFoundError,
    InsufficientPlayersError,
    NotCompetitionCreatorError,
    RoundNotFoundError,
)
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.bloqueos_al_generar import (
    NoGolfCourseForHandicapError,
    NoTeamAssignmentError,
    PlayersNotEnrolledError,
    PlayersWithoutTeeError,
    bloqueo_por,
)
from src.modules.competition.application.services.course_context import course_context_for
from src.modules.competition.application.services.envelope_pairings import (
    EnvelopePairings,
)
from src.modules.competition.application.services.match_players_builder import (
    MatchPlayersBuilder,
)
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.application.services.refresco_rfeg import RefrescoRfeg
from src.modules.competition.application.services.salidas_de_la_ronda import (
    Salidas,
    de_los_partidos,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.barra_del_jugador import (
    BarraDelJugador,
    lo_que_le_falta,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.competition_status import SE_JUEGA
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.match_generation_block import (
    MISSING_ENROLLMENT,
    BlockedPlayer,
    MatchGenerationBlock,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
    TeeRating,
)
from src.shared.domain.services.tee_lookup import TeeKey
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode


class RoundNotPendingMatchesError(Exception):
    """La ronda no está en estado PENDING_MATCHES."""

    pass


def motivo_apuntado(error: Exception) -> MatchGenerationBlock | None:
    """El motivo que el reintento a mano guardó en la sesión por este error.

    El mismo objeto, con su hora: la respuesta no tiene que calcular otro que
    no coincidiría con el de la agenda.
    """
    motivo = getattr(error, "_motivo_apuntado", None)
    return motivo if isinstance(motivo, MatchGenerationBlock) else None


class GenerateMatchesUseCase:
    """
    Caso de uso para generar partidos en una ronda.

    Flujo:
    1. Obtener ronda y competición
    2. Obtener asignación de equipos
    3. Obtener enrollments con handicaps
    4. Obtener campo de golf y tees
    5. Calcular Playing Handicaps (WHS)
    6. Crear partidos (AUTO: por ranking, MANUAL: pairings del request)
    7. Transicionar ronda PENDING_MATCHES → SCHEDULED

    SCRATCH mode: todos playing_handicap=0, strokes_received=()
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
        handicap_calculator: PlayingHandicapCalculator | None = None,
        scoring_service: ScoringService | None = None,
        handicap_service: HandicapService | None = None,
        actividad: CompetitionActivityPublisherInterface | None = None,
    ):
        """
        Args:
            actividad: Los avisos de partido en Actividad (G); sin el, no se avisa
        """
        self._uow = uow
        self._actividad = AvisosDeActividad(actividad)
        # Lo que hay que avisar cuando se guarde: generar va dentro de una
        # transaccion que no es suya (la de abrir los sobres), y avisar antes
        # de confirmarla seria contar partidos que aun pueden deshacerse
        self._salidas_por_avisar: list[tuple[Competition, RoundId, Salidas, Salidas]] = []
        self._gc_repo = golf_course_repository
        self._user_repo = user_repository
        self._calculator = handicap_calculator or PlayingHandicapCalculator()
        self._scoring_service = scoring_service or ScoringService()
        self._refresco_rfeg = RefrescoRfeg(handicap_service, user_repository)
        self._match_players = MatchPlayersBuilder()

    async def execute(
        self,
        request: GenerateMatchesRequestDTO,
        user_id: UserId,
        is_admin: bool = False,
        allow_regeneration: bool = False,
    ) -> GenerateMatchesResponseDTO:
        """
        Args:
            allow_regeneration: Admite una ronda ya en SCHEDULED y la reabre
                DENTRO de esta misma transaccion. Lo usa
                `scripts/regenerate_scheduled_round_strokes.py` para recalcular
                el reparto de golpes de rondas ya montadas. Reabrirla fuera
                dejaria la ronda en PENDING_MATCHES con los partidos viejos si
                la generacion fallara, y las pasadas siguientes la saltarian por
                no estar ya en SCHEDULED.
        """
        async with self._uow:
            # 1. Buscar la ronda
            round_id = RoundId(request.round_id)
            round_entity = await self._uow.rounds.find_by_id(round_id)

            if not round_entity:
                raise RoundNotFoundError(f"No existe ronda con ID {request.round_id}")

            # 2. Buscar la competición
            # Con la fila bloqueada, como al entregar y al abrir sobres: los
            # enfrentamientos de esta sesion pueden salir de ellos (FE #655), y
            # decidirlo mientras un capitan entrega es decidir con datos viejos
            competition = await self._uow.competitions.find_by_id_for_update(
                round_entity.competition_id
            )
            if not competition:
                raise CompetitionNotFoundError("La competición asociada no existe")

            # 3. Verificar creador
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede generar partidos")

            # 4. Verificar la competición: cerrada, o ya en juego (BE #361). Los
            # sobres se abren sesión a sesión, 6 h antes de cada una, así que
            # los de la sesión del domingo se abren con el torneo empezado el
            # sábado: exigir CLOSED dejaba esa sesión sin partidos posibles
            if competition.status not in SE_JUEGA:
                raise CompetitionNotClosedError(
                    "La competición tiene que estar cerrada o en juego para generar "
                    f"partidos. Estado: {competition.status.value}"
                )

            # 5. Verificar ronda PENDING_MATCHES
            fallo: Exception | None = None
            if allow_regeneration:
                if round_entity.status == RoundStatus.SCHEDULED:
                    # La misma transaccion que borra y recrea los partidos: si
                    # algo falla despues, la ronda vuelve sola a SCHEDULED al
                    # deshacerse. Por eso aqui no se apunta ningun motivo
                    round_entity.reopen_for_regeneration()
                matches_created = await self.generar_dentro(
                    round_entity, competition, request.manual_pairings
                )
            else:
                matches_created, fallo = await self._generar_o_apuntar_el_motivo(
                    round_entity, competition, request.manual_pairings
                )

        # Fuera del `with`: el motivo apuntado ya se ha guardado
        if fallo is not None:
            raise fallo

        await self.avisar_salidas()
        return GenerateMatchesResponseDTO(
            round_id=round_entity.id.value,
            matches_generated=matches_created,
            round_status=round_entity.status.value,
        )

    async def _generar_o_apuntar_el_motivo(
        self,
        round_entity: Round,
        competition: Competition,
        manual_pairings: list[ManualPairingDTO] | None,
    ) -> tuple[int, Exception | None]:
        """Genera, o apunta en la sesión por qué no se pudo (BE #360).

        Como al abrir los sobres: lo escrito a medias se deshace con el
        SAVEPOINT y el motivo se guarda con la transacción. Así la tarjeta
        cuenta el fallo de ESTE intento, en el idioma de la pantalla, y no el
        de la apertura.

        Returns:
            Los partidos creados, y el error que devolver si no se pudo
        """
        marca = self.marca_de_salidas()
        try:
            async with self._uow.savepoint():
                return await self.generar_dentro(round_entity, competition, manual_pairings), None
        except Exception as error:
            # Lo deshecho no se avisa
            self.descartar_salidas(desde=marca)
            motivo = bloqueo_por(error, datetime.now(UTC).replace(tzinfo=None))
            if motivo is None:
                raise
            # Todos los motivos saltan antes de tocar la sesión: no hay nada
            # caducado que volver a leer, al contrario que al abrir los sobres
            round_entity.block_match_generation(motivo)
            await self._uow.rounds.update(round_entity)
            # Un atributo ad hoc de la excepción (se lee con `getattr`): con
            # `setattr` el tipo no lo exige declarado en `Exception`
            setattr(error, "_motivo_apuntado", motivo)  # noqa: B010
            return 0, error

    async def generar_dentro(
        self,
        round_entity: Round,
        competition: Competition,
        manual_pairings: list[ManualPairingDTO] | None = None,
        refrescar_handicap_rfeg: bool = True,
    ) -> int:
        """
        Genera los partidos de la sesión en la transacción que ya esté abierta.

        Separado de `execute` para que abrir los sobres pueda crear los
        partidos en su misma transacción (BE #361), sin volver a comprobar
        quién lo pide: ahí no lo pide nadie, lo pide el reloj.

        Args:
            round_entity: La sesión, ya cargada
            competition: Su competición, ya bloqueada
            manual_pairings: Los emparejamientos del organizador, si los manda
            refrescar_handicap_rfeg: Si preguntar a la RFEG por el hándicap de
                cada jugador. Al abrir los sobres NO: eso ocurre dentro de la
                lectura de la pantalla, con la competición bloqueada, y una
                llamada de red por jugador la dejaría colgada

        Returns:
            Cuántos partidos se han creado

        Raises:
            RoundNotPendingMatchesError, NoTeamAssignmentError,
            InsufficientPlayersError, PlayersWithoutTeeError,
            NoGolfCourseForHandicapError, EnvelopesDecideThePairingsError,
            EnvelopesNotRevealedError
        """
        # Una franja de stroke play se reparte en partidas, no en partidos: asignar
        # equipos la pasaría a PENDING_MATCHES como a las demás sesiones (#251)
        if round_entity.hoja_de_salidas is not None:
            raise RoundNotPendingMatchesError(
                "Una franja de un Stableford o un Medal no tiene partidos: se reparte en partidas."
            )
        if not round_entity.can_generate_matches():
            raise RoundNotPendingMatchesError(
                f"La ronda debe estar en PENDING_MATCHES. Estado: {round_entity.status.value}"
            )

        # 6. Obtener asignación de equipos
        team_assignment = await self._uow.team_assignments.find_by_competition(
            round_entity.competition_id
        )
        if not team_assignment:
            raise NoTeamAssignmentError(
                "No hay asignación de equipos. Use AssignTeamsUseCase primero."
            )

        # 7. Obtener enrollments y campo
        enrollments = await self._uow.enrollments.find_by_competition_and_status(
            round_entity.competition_id, EnrollmentStatus.APPROVED
        )

        # Mapear user_id → enrollment
        enrollment_map = {str(e.user_id.value): e for e in enrollments}

        # 8. Obtener campo de golf y tees
        golf_course = await self._gc_repo.find_by_id(round_entity.golf_course_id)

        # 9. Determinar modo de juego
        is_scratch = competition.play_mode == PlayMode.SCRATCH
        allowance = round_entity.get_effective_allowance()
        calculator = self._calculator

        # 10. Construir datos de handicap (tee ratings, holes, user handicaps, genders)
        (
            tee_ratings,
            holes_by_stroke_index,
            user_handicap_map,
            user_gender_map,
            holes_by_tee,
        ) = await self._build_handicap_data(
            golf_course,
            is_scratch,
            team_assignment,
            enrollment_map,
            refrescar_handicap_rfeg,
        )

        players_per_team = round_entity.players_per_team_in_match()
        team_a_ids = list(team_assignment.team_a_player_ids)
        team_b_ids = list(team_assignment.team_b_player_ids)

        max_playing_handicap = competition.max_playing_handicap

        # Los sobres de los capitanes deciden, si los hay (FE #655)
        pairings = await EnvelopePairings.decidir(self._uow, round_entity.id, manual_pairings)

        # Quien no tiene la inscripcion aprobada, antes que las barras: sin
        # inscripcion su color sale del defecto y su falta pareceria otra
        if pairings:
            await self._comprobar_inscripciones(pairings, enrollment_map, competition)

        # Antes de escribir nada, todos los que no tienen barras: de uno en uno,
        # arreglar a doce jugadores eran doce viajes (BE #360)
        if not is_scratch:
            await self._comprobar_que_todos_tienen_barras(
                self._jugadores_que_juegan(pairings, team_a_ids, team_b_ids, players_per_team),
                competition=competition,
                enrollment_map=enrollment_map,
                tee_ratings=tee_ratings,
                user_handicap_map=user_handicap_map,
                user_gender_map=user_gender_map,
            )

        # 11. Eliminar partidos existentes (re-generación)
        existing_matches = await self._uow.matches.find_by_round(round_entity.id)
        for m in existing_matches:
            await self._uow.matches.delete(m.id)

        if existing_matches:
            await self._uow.flush()  # Forzar DELETE antes de INSERT (unique constraint)

        # 12. Generar partidos
        if pairings:
            creados = await self._generate_manual(
                pairings,
                round_entity,
                enrollment_map,
                tee_ratings,
                calculator,
                allowance,
                is_scratch,
                user_handicap_map,
                holes_by_stroke_index,
                user_gender_map,
                max_playing_handicap,
                holes_by_tee,
            )
        else:
            creados = await self._generate_auto(
                round_entity,
                team_a_ids,
                team_b_ids,
                enrollment_map,
                tee_ratings,
                calculator,
                allowance,
                is_scratch,
                players_per_team,
                user_handicap_map,
                holes_by_stroke_index,
                user_gender_map,
                max_playing_handicap,
                holes_by_tee,
            )

        # 13. Transicionar ronda
        round_entity.mark_matches_generated()
        await self._uow.rounds.update(round_entity)
        # Se avisa al guardar, y solo a quien le cambia algo: regenerar los
        # mismos emparejamientos no avisa a nadie (G2, G3)
        self._salidas_por_avisar.append(
            (
                competition,
                round_entity.id,
                de_los_partidos(round_entity, existing_matches),
                de_los_partidos(round_entity, creados),
            )
        )
        return len(creados)

    async def avisar_salidas(self) -> None:
        """
        Avisa de los partidos generados, ya guardados (G2). Quien genera dentro
        de su transaccion —abrir los sobres— lo llama tras confirmarla.
        """
        pendientes, self._salidas_por_avisar = self._salidas_por_avisar, []
        for competition, round_id, antes, despues in pendientes:
            await self._actividad.salidas_cambiadas(competition, round_id, antes, despues)

    def marca_de_salidas(self) -> int:
        """Hasta donde llega lo pendiente de avisar: para descartar solo lo que venga despues."""
        return len(self._salidas_por_avisar)

    def descartar_salidas(self, desde: int) -> None:
        """
        Lo generado desde `desde` se deshizo: eso no se avisa. Lo de antes
        —otra sesion abierta en la misma lectura— sigue en pie (revision del
        22 oct 2026).
        """
        del self._salidas_por_avisar[desde:]

    async def _comprobar_inscripciones(
        self,
        pairings: list[ManualPairingDTO],
        enrollment_map: Mapping[str, Enrollment],
        competition: Competition,
    ) -> None:
        """Todos los emparejados tienen que tener la inscripción aprobada.

        Raises:
            PlayersNotEnrolledError: Con TODOS los que no la tienen, y su
                nombre: de uno en uno eran tantos viajes como retirados
        """
        sin_inscripcion = [
            UserId(uid)
            for pairing in pairings
            for uid in [*pairing.team_a_player_ids, *pairing.team_b_player_ids]
            if str(uid) not in enrollment_map
        ]
        if not sin_inscripcion:
            return
        nombres = await PlayerNames.de_la_competicion(
            sin_inscripcion, competition.id, self._user_repo, self._uow
        )
        raise PlayersNotEnrolledError(
            [
                BlockedPlayer(user_id=uid, name=nombres.get(uid, ""), missing=MISSING_ENROLLMENT)
                for uid in sin_inscripcion
            ]
        )

    @staticmethod
    def _jugadores_que_juegan(
        pairings: list[ManualPairingDTO] | None,
        team_a_ids: list[UserId],
        team_b_ids: list[UserId],
        players_per_team: int,
    ) -> list[UserId]:
        """Quién va a jugar esta sesión, en el orden en que saldrá.

        Con emparejamientos, los que traen; sin ellos, los que caben en los
        partidos que salen del reparto por ranking.
        """
        if pairings:
            return [
                UserId(uid)
                for pairing in pairings
                for uid in [*pairing.team_a_player_ids, *pairing.team_b_player_ids]
            ]
        caben = min(len(team_a_ids), len(team_b_ids)) // players_per_team * players_per_team
        return [*team_a_ids[:caben], *team_b_ids[:caben]]

    async def _comprobar_que_todos_tienen_barras(
        self,
        jugadores: list[UserId],
        *,
        competition: Competition,
        enrollment_map: Mapping[str, Enrollment],
        tee_ratings: Mapping[TeeKey, TeeRating],
        user_handicap_map: Mapping[str, Decimal],
        user_gender_map: Mapping[str, Gender | None],
    ) -> None:
        """
        Raises:
            PlayersWithoutTeeError: Con TODOS los que no tienen barras en el
                campo, y lo que le falta a cada uno
        """
        sin_barras = []
        for uid in jugadores:
            tee_color, _, tee_rating, _ = self._match_players.resolve_player_data(
                uid, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
            )
            falta = lo_que_le_falta(
                BarraDelJugador(tee_color, None, tee_rating),
                user_gender_map.get(str(uid.value)),
                tee_ratings,
            )
            if falta is not None:
                sin_barras.append((uid, *falta))
        if not sin_barras:
            return

        nombres = await PlayerNames.de_la_competicion(
            [uid for uid, _, _ in sin_barras], competition.id, self._user_repo, self._uow
        )
        raise PlayersWithoutTeeError(
            [
                BlockedPlayer(
                    user_id=uid, name=nombres.get(uid, ""), missing=missing, tee_color=color
                )
                for uid, missing, color in sin_barras
            ]
        )

    async def _build_handicap_data(
        self,
        golf_course: GolfCourse | None,
        is_scratch: bool,
        team_assignment: TeamAssignment,
        enrollment_map: Mapping[str, Enrollment],
        refrescar_handicap_rfeg: bool = True,
    ) -> tuple[
        dict[TeeKey, TeeRating],
        list[int],
        dict[str, Decimal],
        dict[str, Gender | None],
        dict[TeeKey, list[int]],
    ]:
        """Pre-fetch tee ratings, hole stroke order, user handicaps, and user genders."""
        tee_ratings: dict[tuple[str, str | None], TeeRating] = {}
        holes_by_stroke_index: list[int] = []
        holes_by_tee: dict[tuple[str, str | None], list[int]] = {}
        user_handicap_map: dict[str, Decimal] = {}
        user_gender_map: dict[str, Gender | None] = {}

        if not is_scratch and not golf_course:
            raise NoGolfCourseForHandicapError(
                "Se requiere un campo de golf para el modo HANDICAP. "
                "Asocie un campo de golf aprobado a la competición."
            )

        # También en SCRATCH: sin golpes, pero cada uno guarda el género de su
        # barra, y con él su tarjeta y las muestras del mapa (RyderCupWeb #880)
        if golf_course:
            context = course_context_for(golf_course)
            tee_ratings = context.tee_ratings
            holes_by_stroke_index = context.holes_by_stroke_index
            holes_by_tee = context.holes_by_tee

        if golf_course or not is_scratch:
            all_player_ids = list(team_assignment.team_a_player_ids) + list(
                team_assignment.team_b_player_ids
            )
            # De uno en uno: son consultas sobre la misma sesión, y SQLAlchemy
            # no admite dos operaciones a la vez en una sesión (era un gather)
            users = [await self._user_repo.find_by_id(pid) for pid in all_player_ids]
            for pid, user in zip(all_player_ids, users, strict=True):
                if user:
                    enrollment = enrollment_map.get(str(pid.value))
                    has_custom_handicap = (
                        enrollment is not None and enrollment.has_custom_handicap()
                    )
                    if not is_scratch and not has_custom_handicap and refrescar_handicap_rfeg:
                        await self._refresco_rfeg.si_toca(user)
                    # En SCRATCH solo el género: el hándicap no cuenta
                    if not is_scratch and user.handicap is not None:
                        user_handicap_map[str(pid.value)] = Decimal(str(user.handicap.value))
                    user_gender_map[str(pid.value)] = user.gender

        return (
            tee_ratings,
            holes_by_stroke_index,
            user_handicap_map,
            user_gender_map,
            holes_by_tee,
        )

    async def _generate_auto(
        self,
        round_entity: Round,
        team_a_ids: list[UserId],
        team_b_ids: list[UserId],
        enrollment_map: Mapping[str, Enrollment],
        tee_ratings: Mapping[TeeKey, TeeRating],
        calculator: PlayingHandicapCalculator,
        allowance: int,
        is_scratch: bool,
        players_per_team: int,
        user_handicap_map: Mapping[str, Decimal],
        holes_by_stroke_index: list[int],
        user_gender_map: Mapping[str, Gender | None],
        max_playing_handicap: int | None = None,
        holes_by_tee: Mapping[TeeKey, list[int]] | None = None,
    ) -> list[Match]:
        """Genera partidos automáticamente emparejando por ranking."""
        # Para SINGLES: 1v1, para FOURBALL/FOURSOMES: 2v2
        num_matches = min(len(team_a_ids), len(team_b_ids)) // players_per_team
        if num_matches == 0:
            raise InsufficientPlayersError(
                f"No hay suficientes jugadores para formato "
                f"{round_entity.match_format.value} ({players_per_team} por equipo)"
            )

        match_format = round_entity.match_format

        creados: list[Match] = []
        for i in range(num_matches):
            start = i * players_per_team
            end = start + players_per_team

            a_players_ids = team_a_ids[start:end]
            b_players_ids = team_b_ids[start:end]

            team_a_match_players, team_b_match_players = self._match_players.build(
                match_format,
                a_players_ids,
                b_players_ids,
                enrollment_map,
                tee_ratings,
                calculator,
                allowance,
                is_scratch,
                user_handicap_map,
                holes_by_stroke_index,
                user_gender_map,
                max_playing_handicap,
                holes_by_tee,
            )
            match = Match.create(
                round_id=round_entity.id,
                match_number=i + 1,
                team_a_players=team_a_match_players,
                team_b_players=team_b_match_players,
            )
            # Generate marker assignments for scoring
            marker_assignments = self._scoring_service.generate_marker_assignments(
                match.team_a_players, match.team_b_players, round_entity.match_format
            )
            match.set_marker_assignments(marker_assignments)
            await self._uow.matches.add(match)
            creados.append(match)

        return creados

    async def _generate_manual(
        self,
        pairings: list[ManualPairingDTO],
        round_entity: Round,
        enrollment_map: Mapping[str, Enrollment],
        tee_ratings: Mapping[TeeKey, TeeRating],
        calculator: PlayingHandicapCalculator,
        allowance: int,
        is_scratch: bool,
        user_handicap_map: Mapping[str, Decimal],
        holes_by_stroke_index: list[int],
        user_gender_map: Mapping[str, Gender | None],
        max_playing_handicap: int | None = None,
        holes_by_tee: Mapping[TeeKey, list[int]] | None = None,
    ) -> list[Match]:
        """Genera partidos según emparejamientos ya decididos.

        Los trae el organizador en la petición, o los fijan los sobres de los
        capitanes cuando ya se abrieron (FE #655).
        """
        match_format = round_entity.match_format

        creados: list[Match] = []
        for i, pairing in enumerate(pairings):
            a_ids = [UserId(uid) for uid in pairing.team_a_player_ids]
            b_ids = [UserId(uid) for uid in pairing.team_b_player_ids]

            team_a_match_players, team_b_match_players = self._match_players.build(
                match_format,
                a_ids,
                b_ids,
                enrollment_map,
                tee_ratings,
                calculator,
                allowance,
                is_scratch,
                user_handicap_map,
                holes_by_stroke_index,
                user_gender_map,
                max_playing_handicap,
                holes_by_tee,
            )

            match = Match.create(
                round_id=round_entity.id,
                match_number=i + 1,
                team_a_players=team_a_match_players,
                team_b_players=team_b_match_players,
            )
            # Generate marker assignments for scoring
            marker_assignments = self._scoring_service.generate_marker_assignments(
                match.team_a_players, match.team_b_players, round_entity.match_format
            )
            match.set_marker_assignments(marker_assignments)
            await self._uow.matches.add(match)
            creados.append(match)

        return creados
