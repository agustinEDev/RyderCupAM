"""Caso de Uso: Generar partidos para una ronda."""

import asyncio
from decimal import Decimal

from src.modules.competition.application.dto.round_match_dto import (
    GenerateMatchesRequestDTO,
    GenerateMatchesResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotClosedError,
    CompetitionNotFoundError,
    InsufficientPlayersError,
    NotCompetitionCreatorError,
    RoundNotFoundError,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
    TeeRating,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


class RoundNotPendingMatchesError(Exception):
    """La ronda no está en estado PENDING_MATCHES."""

    pass


class NoTeamAssignmentError(Exception):
    """No hay asignación de equipos."""

    pass


class TeeCategoryNotFoundError(Exception):
    """No se encontró la categoría de tee del jugador en el campo."""

    pass


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
    ):
        self._uow = uow
        self._gc_repo = golf_course_repository
        self._user_repo = user_repository
        self._calculator = handicap_calculator or PlayingHandicapCalculator()
        self._scoring_service = scoring_service or ScoringService()

    async def execute(
        self, request: GenerateMatchesRequestDTO, user_id: UserId
    ) -> GenerateMatchesResponseDTO:
        async with self._uow:
            # 1. Buscar la ronda
            round_id = RoundId(request.round_id)
            round_entity = await self._uow.rounds.find_by_id(round_id)

            if not round_entity:
                raise RoundNotFoundError(f"No existe ronda con ID {request.round_id}")

            # 2. Buscar la competición
            competition = await self._uow.competitions.find_by_id(round_entity.competition_id)
            if not competition:
                raise CompetitionNotFoundError("La competición asociada no existe")

            # 3. Verificar creador
            if not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede generar partidos")

            # 4. Verificar competición CLOSED
            if competition.status != CompetitionStatus.CLOSED:
                raise CompetitionNotClosedError(
                    f"La competición debe estar en CLOSED. Estado: {competition.status.value}"
                )

            # 5. Verificar ronda PENDING_MATCHES
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
            ) = await self._build_handicap_data(
                golf_course,
                is_scratch,
                team_assignment,
            )

            # 11. Eliminar partidos existentes (re-generación)
            existing_matches = await self._uow.matches.find_by_round(round_id)
            for m in existing_matches:
                await self._uow.matches.delete(m.id)

            if existing_matches:
                await self._uow.flush()  # Forzar DELETE antes de INSERT (unique constraint)

            # 12. Generar partidos
            players_per_team = round_entity.players_per_team_in_match()
            team_a_ids = list(team_assignment.team_a_player_ids)
            team_b_ids = list(team_assignment.team_b_player_ids)

            if request.manual_pairings:
                matches_created = await self._generate_manual(
                    request,
                    round_entity,
                    enrollment_map,
                    tee_ratings,
                    calculator,
                    allowance,
                    is_scratch,
                    user_handicap_map,
                    holes_by_stroke_index,
                    user_gender_map,
                )
            else:
                matches_created = await self._generate_auto(
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
                )

            # 13. Transicionar ronda
            round_entity.mark_matches_generated()
            await self._uow.rounds.update(round_entity)

        return GenerateMatchesResponseDTO(
            round_id=round_entity.id.value,
            matches_generated=matches_created,
            round_status=round_entity.status.value,
        )

    async def _build_handicap_data(self, golf_course, is_scratch, team_assignment):
        """Pre-fetch tee ratings, hole stroke order, user handicaps, and user genders."""
        tee_ratings: dict[tuple[str, str | None], TeeRating] = {}
        holes_by_stroke_index: list[int] = []
        user_handicap_map: dict[str, Decimal] = {}
        user_gender_map: dict[str, Gender | None] = {}

        if not is_scratch and not golf_course:
            raise ValueError(
                "Se requiere un campo de golf para el modo HANDICAP. "
                "Asocie un campo de golf aprobado a la competición."
            )

        if golf_course and not is_scratch:
            for tee in golf_course.tees:
                total_par = sum(h.par for h in golf_course.holes)
                gender_key = tee.gender.value if tee.gender else None
                tee_ratings[(tee.category.value, gender_key)] = TeeRating(
                    course_rating=Decimal(str(tee.course_rating)),
                    slope_rating=tee.slope_rating,
                    par=total_par,
                )
            holes_by_stroke_index = [
                h.number for h in sorted(golf_course.holes, key=lambda h: h.stroke_index)
            ]

        if not is_scratch:
            all_player_ids = list(team_assignment.team_a_player_ids) + list(
                team_assignment.team_b_player_ids
            )
            users = await asyncio.gather(
                *(self._user_repo.find_by_id(pid) for pid in all_player_ids)
            )
            for pid, user in zip(all_player_ids, users, strict=True):
                if user:
                    if user.handicap is not None:
                        user_handicap_map[str(pid.value)] = Decimal(str(user.handicap.value))
                    user_gender_map[str(pid.value)] = user.gender

        return tee_ratings, holes_by_stroke_index, user_handicap_map, user_gender_map

    async def _generate_auto(
        self,
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
    ):
        """Genera partidos automáticamente emparejando por ranking."""
        # Para SINGLES: 1v1, para FOURBALL/FOURSOMES: 2v2
        num_matches = min(len(team_a_ids), len(team_b_ids)) // players_per_team
        if num_matches == 0:
            raise InsufficientPlayersError(
                f"No hay suficientes jugadores para formato "
                f"{round_entity.match_format.value} ({players_per_team} por equipo)"
            )

        match_format = round_entity.match_format

        matches_created = 0
        for i in range(num_matches):
            start = i * players_per_team
            end = start + players_per_team

            a_players_ids = team_a_ids[start:end]
            b_players_ids = team_b_ids[start:end]

            if match_format == MatchFormat.FOURBALL:
                team_a_match_players, team_b_match_players = self._build_fourball_match_players(
                    a_players_ids, b_players_ids, enrollment_map, tee_ratings,
                    calculator, allowance, is_scratch, user_handicap_map,
                    holes_by_stroke_index, user_gender_map,
                )
            elif match_format == MatchFormat.FOURSOMES:
                team_a_match_players, team_b_match_players = self._build_foursomes_match_players(
                    a_players_ids, b_players_ids, enrollment_map, tee_ratings,
                    calculator, allowance, is_scratch, user_handicap_map,
                    holes_by_stroke_index, user_gender_map,
                )
            else:
                # SINGLES: allowance individual por jugador
                team_a_match_players = [
                    self._build_match_player(
                        uid, enrollment_map, tee_ratings, calculator, allowance,
                        is_scratch, user_handicap_map, holes_by_stroke_index, user_gender_map,
                    )
                    for uid in a_players_ids
                ]
                team_b_match_players = [
                    self._build_match_player(
                        uid, enrollment_map, tee_ratings, calculator, allowance,
                        is_scratch, user_handicap_map, holes_by_stroke_index, user_gender_map,
                    )
                    for uid in b_players_ids
                ]

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
            matches_created += 1

        return matches_created

    async def _generate_manual(
        self,
        request,
        round_entity,
        enrollment_map,
        tee_ratings,
        calculator,
        allowance,
        is_scratch,
        user_handicap_map,
        holes_by_stroke_index,
        user_gender_map,
    ):
        """Genera partidos según emparejamientos manuales."""
        # Validar que todos los jugadores estén inscritos (APPROVED)
        for pairing in request.manual_pairings:
            for uid in list(pairing.team_a_player_ids) + list(pairing.team_b_player_ids):
                if str(uid) not in enrollment_map:
                    raise InsufficientPlayersError(
                        f"El jugador {uid} no tiene inscripción aprobada"
                    )

        match_format = round_entity.match_format

        matches_created = 0
        for i, pairing in enumerate(request.manual_pairings):
            a_ids = [UserId(uid) for uid in pairing.team_a_player_ids]
            b_ids = [UserId(uid) for uid in pairing.team_b_player_ids]

            if match_format == MatchFormat.FOURBALL:
                team_a_match_players, team_b_match_players = self._build_fourball_match_players(
                    a_ids, b_ids, enrollment_map, tee_ratings,
                    calculator, allowance, is_scratch, user_handicap_map,
                    holes_by_stroke_index, user_gender_map,
                )
            elif match_format == MatchFormat.FOURSOMES:
                team_a_match_players, team_b_match_players = self._build_foursomes_match_players(
                    a_ids, b_ids, enrollment_map, tee_ratings,
                    calculator, allowance, is_scratch, user_handicap_map,
                    holes_by_stroke_index, user_gender_map,
                )
            else:
                # SINGLES: allowance individual por jugador
                team_a_match_players = [
                    self._build_match_player(
                        uid, enrollment_map, tee_ratings, calculator, allowance,
                        is_scratch, user_handicap_map, holes_by_stroke_index, user_gender_map,
                    )
                    for uid in a_ids
                ]
                team_b_match_players = [
                    self._build_match_player(
                        uid, enrollment_map, tee_ratings, calculator, allowance,
                        is_scratch, user_handicap_map, holes_by_stroke_index, user_gender_map,
                    )
                    for uid in b_ids
                ]

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
            matches_created += 1

        return matches_created

    def _resolve_player_data(
        self,
        user_id,
        enrollment_map,
        tee_ratings,
        user_handicap_map,
        user_gender_map,
    ) -> tuple[TeeCategory, Gender | None, TeeRating | None, Decimal]:
        """
        Resuelve datos de un jugador: tee category, gender, tee rating e handicap index.

        Returns:
            (tee_category, tee_gender, tee_rating, handicap_index)
        """
        enrollment = enrollment_map.get(str(user_id.value))
        tee_category = (
            enrollment.tee_category
            if enrollment and enrollment.tee_category
            else TeeCategory.AMATEUR
        )
        user_gender = user_gender_map.get(str(user_id.value))

        # Auto-resolve tee: (category, user_gender) → (category, None) fallback
        tee_gender = user_gender
        tee_key = (tee_category.value, tee_gender.value if tee_gender else None)
        if tee_key not in tee_ratings:
            tee_key = (tee_category.value, None)
            tee_gender = None

        tee_rating = tee_ratings.get(tee_key)

        # Handicap fallback: custom_handicap > user.handicap > 0
        if enrollment and enrollment.custom_handicap is not None:
            handicap_index = enrollment.custom_handicap
        elif str(user_id.value) in user_handicap_map:
            handicap_index = user_handicap_map[str(user_id.value)]
        else:
            handicap_index = Decimal("0")

        return tee_category, tee_gender, tee_rating, handicap_index

    def _build_match_player(
        self,
        user_id,
        enrollment_map,
        tee_ratings,
        calculator,
        allowance,
        is_scratch,
        user_handicap_map,
        holes_by_stroke_index,
        user_gender_map,
    ) -> MatchPlayer:
        """Construye un MatchPlayer con handicap calculado y tee auto-resuelto."""
        tee_category, tee_gender, tee_rating, handicap_index = self._resolve_player_data(
            user_id, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
        )

        if is_scratch:
            return MatchPlayer.create(
                user_id=user_id,
                playing_handicap=0,
                tee_category=tee_category,
                strokes_received=[],
                tee_gender=tee_gender,
            )

        if not tee_rating:
            raise TeeCategoryNotFoundError(
                f"No se encontró tee rating para categoría '{tee_category.value}' "
                f"(gender: {tee_gender}) en el campo de golf"
            )

        playing_handicap = calculator.calculate(handicap_index, tee_rating, allowance)
        strokes_received = calculator.compute_strokes_received(playing_handicap, holes_by_stroke_index)

        return MatchPlayer.create(
            user_id=user_id,
            playing_handicap=playing_handicap,
            tee_category=tee_category,
            strokes_received=strokes_received,
            tee_gender=tee_gender,
        )

    def _build_fourball_match_players(
        self,
        team_a_ids,
        team_b_ids,
        enrollment_map,
        tee_ratings,
        calculator,
        allowance,
        is_scratch,
        user_handicap_map,
        holes_by_stroke_index,
        user_gender_map,
    ) -> tuple[list[MatchPlayer], list[MatchPlayer]]:
        """
        Construye MatchPlayers para FOURBALL usando el método diferencial WHS.

        En lugar de aplicar allowance% al CH individual, calcula las diferencias
        respecto al menor CH de los 4 jugadores y aplica allowance% a esas diferencias.

        Returns:
            (team_a_match_players, team_b_match_players)
        """
        all_ids = list(team_a_ids) + list(team_b_ids)

        if is_scratch:
            # En modo SCRATCH, todos juegan off scratch
            team_a_players = []
            for uid in team_a_ids:
                tee_cat, tee_gen, _, _ = self._resolve_player_data(
                    uid, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
                )
                team_a_players.append(MatchPlayer.create(
                    user_id=uid, playing_handicap=0, tee_category=tee_cat,
                    strokes_received=[], tee_gender=tee_gen,
                ))
            team_b_players = []
            for uid in team_b_ids:
                tee_cat, tee_gen, _, _ = self._resolve_player_data(
                    uid, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
                )
                team_b_players.append(MatchPlayer.create(
                    user_id=uid, playing_handicap=0, tee_category=tee_cat,
                    strokes_received=[], tee_gender=tee_gen,
                ))
            return team_a_players, team_b_players

        # 1. Calcular Course Handicaps (100%, sin allowance) para los 4 jugadores
        player_data: dict[str, tuple[TeeCategory, Gender | None, TeeRating, Decimal]] = {}
        course_handicaps: list[tuple[str, int]] = []

        for uid in all_ids:
            tee_cat, tee_gen, tee_rating, hi = self._resolve_player_data(
                uid, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
            )
            if not tee_rating:
                raise TeeCategoryNotFoundError(
                    f"No se encontró tee rating para categoría '{tee_cat.value}' "
                    f"(gender: {tee_gen}) en el campo de golf"
                )
            player_data[str(uid.value)] = (tee_cat, tee_gen, tee_rating, hi)
            ch = calculator.calculate_course_handicap(hi, tee_rating)
            course_handicaps.append((str(uid.value), ch))

        # 2. Método diferencial: aplica allowance% a diferencias respecto al menor CH
        differential_phs = calculator.calculate_fourball_differential(
            course_handicaps, allowance
        )

        # 3. Construir MatchPlayers con PH diferencial
        def build_player(uid):
            uid_str = str(uid.value)
            tee_cat, tee_gen, _, _ = player_data[uid_str]
            ph = differential_phs[uid_str]
            strokes = calculator.compute_strokes_received(ph, holes_by_stroke_index)
            return MatchPlayer.create(
                user_id=uid, playing_handicap=ph, tee_category=tee_cat,
                strokes_received=strokes, tee_gender=tee_gen,
            )

        team_a_players = [build_player(uid) for uid in team_a_ids]
        team_b_players = [build_player(uid) for uid in team_b_ids]
        return team_a_players, team_b_players

    def _build_foursomes_match_players(
        self,
        team_a_ids,
        team_b_ids,
        enrollment_map,
        tee_ratings,
        calculator,
        allowance,
        is_scratch,
        user_handicap_map,
        holes_by_stroke_index,
        user_gender_map,
    ) -> tuple[list[MatchPlayer], list[MatchPlayer]]:
        """
        Construye MatchPlayers para FOURSOMES usando el método diferencial WHS.

        En FOURSOMES (golpe alterno) los strokes se calculan a nivel de EQUIPO:
        1. Se calcula el CH individual de cada jugador (100%, sin allowance)
        2. Se promedian los CH por equipo
        3. Se aplica el allowance% a la diferencia entre promedios
        4. Solo el equipo con mayor CH promedio recibe strokes
        5. Ambos jugadores del equipo comparten los mismos strokes (una bola)

        Returns:
            (team_a_match_players, team_b_match_players)
        """
        all_ids = list(team_a_ids) + list(team_b_ids)

        if is_scratch:
            team_a_players = []
            for uid in team_a_ids:
                tee_cat, tee_gen, _, _ = self._resolve_player_data(
                    uid, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
                )
                team_a_players.append(MatchPlayer.create(
                    user_id=uid, playing_handicap=0, tee_category=tee_cat,
                    strokes_received=[], tee_gender=tee_gen,
                ))
            team_b_players = []
            for uid in team_b_ids:
                tee_cat, tee_gen, _, _ = self._resolve_player_data(
                    uid, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
                )
                team_b_players.append(MatchPlayer.create(
                    user_id=uid, playing_handicap=0, tee_category=tee_cat,
                    strokes_received=[], tee_gender=tee_gen,
                ))
            return team_a_players, team_b_players

        # 1. Calcular Course Handicaps individuales (100%, sin allowance)
        player_data: dict[str, tuple[TeeCategory, Gender | None]] = {}
        team_a_chs: list[int] = []
        team_b_chs: list[int] = []

        for uid in all_ids:
            tee_cat, tee_gen, tee_rating, hi = self._resolve_player_data(
                uid, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
            )
            if not tee_rating:
                raise TeeCategoryNotFoundError(
                    f"No se encontró tee rating para categoría '{tee_cat.value}' "
                    f"(gender: {tee_gen}) en el campo de golf"
                )
            player_data[str(uid.value)] = (tee_cat, tee_gen)
            ch = calculator.calculate_course_handicap(hi, tee_rating)
            if uid in team_a_ids:
                team_a_chs.append(ch)
            else:
                team_b_chs.append(ch)

        # 2. Método diferencial por equipos: allowance% se aplica a la diferencia de promedios
        team_a_ph, team_b_ph = calculator.calculate_foursomes_differential(
            team_a_chs, team_b_chs, allowance
        )

        # 3. Ambos jugadores del equipo comparten los mismos strokes (una bola)
        team_a_strokes = calculator.compute_strokes_received(team_a_ph, holes_by_stroke_index)
        team_b_strokes = calculator.compute_strokes_received(team_b_ph, holes_by_stroke_index)

        team_a_players = []
        for uid in team_a_ids:
            tee_cat, tee_gen = player_data[str(uid.value)]
            team_a_players.append(MatchPlayer.create(
                user_id=uid, playing_handicap=team_a_ph, tee_category=tee_cat,
                strokes_received=team_a_strokes, tee_gender=tee_gen,
            ))

        team_b_players = []
        for uid in team_b_ids:
            tee_cat, tee_gen = player_data[str(uid.value)]
            team_b_players.append(MatchPlayer.create(
                user_id=uid, playing_handicap=team_b_ph, tee_category=tee_cat,
                strokes_received=team_b_strokes, tee_gender=tee_gen,
            ))

        return team_a_players, team_b_players

