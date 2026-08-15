"""Caso de Uso: Obtener el detalle de una Partida Rapida (con scores y standing)."""

from decimal import Decimal

from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.quick_match.application.dto.quick_match_dto import (
    HoleScoreResponseDTO,
    ParticipantStrokesDTO,
    QuickMatchDetailResponseDTO,
    QuickMatchStandingResponseDTO,
    ScoringAssignmentDTO,
)
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchParticipantError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.mappers.quick_match_mapper import QuickMatchDTOMapper
from src.modules.quick_match.application.services.stroke_context_builder import (
    StrokeContextBuilder,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.services.scoring_coverage_service import (
    ScoringCoverageService,
)
from src.modules.quick_match.domain.services.stroke_allocation_service import (
    ParticipantStrokes,
    StrokeAllocationService,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

TOTAL_HOLES = 18


class GetQuickMatchUseCase:
    """Obtiene el detalle de una partida rapida: datos, scores, standing y reparto de anotacion."""

    def __init__(
        self,
        uow: QuickMatchUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        scoring_service: ScoringService,
        coverage_service: ScoringCoverageService,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
        stroke_allocation_service: StrokeAllocationService | None = None,
    ):
        self._uow = uow
        self._user_uow = user_uow
        self._scoring_service = scoring_service
        self._coverage_service = coverage_service
        self._golf_course_uow = golf_course_uow
        self._stroke_allocation_service = stroke_allocation_service or StrokeAllocationService()

    async def execute(
        self, quick_match_id_raw: str, current_user_id_raw: str
    ) -> QuickMatchDetailResponseDTO:
        current_participant_id = ParticipantId(UserId(current_user_id_raw).value)

        async with self._uow:
            quick_match = await self._uow.quick_matches.find_by_id(QuickMatchId(quick_match_id_raw))
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {quick_match_id_raw}")

            if not quick_match.is_participant(current_participant_id):
                raise NotQuickMatchParticipantError(
                    "You are not a participant of this quick match."
                )

            hole_scores = await self._uow.quick_match_hole_scores.find_by_match(quick_match.id)

        registered_ids = [p.user_id for p in quick_match.participants if p.user_id is not None]
        async with self._user_uow:
            users_by_id = {}
            for user_id in registered_ids:
                user = await self._user_uow.users.find_by_id(user_id)
                if user:
                    users_by_id[user_id] = user

        base_dto = await QuickMatchDTOMapper.to_response_dto(
            quick_match, self._user_uow, users_by_id=users_by_id
        )

        hole_scores_dto = [
            HoleScoreResponseDTO(
                hole_number=hs.hole_number,
                participant_id=hs.participant_id.value,
                score=hs.score,
                recorded_by_participant_id=hs.recorded_by_participant_id.value,
            )
            for hs in sorted(hole_scores, key=lambda h: h.hole_number)
        ]

        strokes_by_participant = await self._allocate_strokes(quick_match, users_by_id)
        standing_dto = self._compute_standing(quick_match, hole_scores, strokes_by_participant)
        assignments_dto = self._build_assignments(quick_match, users_by_id)

        return QuickMatchDetailResponseDTO(
            **base_dto.model_dump(),
            hole_scores=hole_scores_dto,
            standing=standing_dto,
            scoring_assignments=assignments_dto,
            participant_strokes=[
                ParticipantStrokesDTO(
                    participant_id=ps.participant_id.value,
                    playing_handicap=ps.playing_handicap,
                    strokes_received=list(ps.strokes_received),
                )
                for ps in strokes_by_participant.values()
            ],
        )

    async def _allocate_strokes(
        self, quick_match, users_by_id
    ) -> dict[ParticipantId, ParticipantStrokes]:
        """
        Reparte los golpes de handicap de la partida.

        Si el campo no se puede cargar se devuelve un reparto vacio en vez de
        fallar: perder los puntitos de la tarjeta es mucho menos grave que dejar
        la partida inaccesible mientras se esta jugando.
        """
        async with self._golf_course_uow:
            golf_course = await self._golf_course_uow.golf_courses.find_by_id(
                quick_match.golf_course_id
            )

        if golf_course is None:
            return {
                p.participant_id: ParticipantStrokes(p.participant_id, 0, ())
                for p in quick_match.participants
            }

        context = StrokeContextBuilder.build(golf_course)
        return self._stroke_allocation_service.allocate(
            participants=quick_match.participants,
            handicaps=self._resolve_handicaps(quick_match, users_by_id),
            tee_ratings=context.tee_ratings,
            holes_by_stroke_index=context.holes_by_stroke_index,
            match_format=quick_match.match_format,
            allowance_percentage=quick_match.get_effective_allowance(),
            play_mode=quick_match.play_mode,
        )

    @staticmethod
    def _resolve_handicaps(quick_match, users_by_id) -> dict[ParticipantId, Decimal | None]:
        """
        Handicap Index efectivo de cada participante.

        Misma precedencia que el mapper de presentacion: el override manual del
        creador gana al del perfil, y un invitado solo tiene el manual.
        """
        handicaps: dict[ParticipantId, Decimal | None] = {}
        for p in quick_match.participants:
            if p.is_guest:
                raw = p.handicap
            elif p.custom_handicap is not None:
                raw = p.custom_handicap
            else:
                user = users_by_id.get(p.user_id)
                raw = user.handicap.value if user and user.handicap else None
            handicaps[p.participant_id] = None if raw is None else Decimal(str(raw))
        return handicaps

    def _build_assignments(self, quick_match, users_by_id) -> list[ScoringAssignmentDTO]:
        if not quick_match.scorer_ids:
            return []

        assignments = self._coverage_service.compute_assignments(
            participants=quick_match.participants,
            scorer_ids=quick_match.scorer_ids,
            creator_participant_id=quick_match.creator_participant_id,
        )

        result = []
        for scorer_id, covered_ids in assignments.items():
            scorer = quick_match.find_participant(scorer_id)
            user = users_by_id.get(scorer.user_id) if scorer else None
            scorer_name = f"{user.first_name} {user.last_name}" if user else "Unknown"
            result.append(
                ScoringAssignmentDTO(
                    scorer_participant_id=scorer_id.value,
                    scorer_name=scorer_name,
                    covered_participant_ids=[cid.value for cid in covered_ids],
                )
            )
        return result

    def _compute_standing(
        self,
        quick_match,
        hole_scores,
        strokes_by_participant: dict[ParticipantId, ParticipantStrokes],
    ) -> QuickMatchStandingResponseDTO | None:
        if quick_match.match_format is None:
            # Partido libre (MEDAL/STABLEFORD): sin equipos, no hay standing A-vs-B.
            # La clasificacion individual se calcula en el frontend a partir de hole_scores.
            return None

        rosters = quick_match.team_rosters()
        if rosters is None:
            return None
        team_a_ids, team_b_ids = rosters

        scores_by_hole: dict[int, dict] = {}
        for hs in hole_scores:
            scores_by_hole.setdefault(hs.hole_number, {})[hs.participant_id] = hs.score

        hole_results = []
        for hole_number in range(1, TOTAL_HOLES + 1):
            scores = scores_by_hole.get(hole_number)
            if not scores:
                continue
            if not all(pid in scores for pid in team_a_ids | team_b_ids):
                continue

            # `calculate_hole_winner` compara scores NETOS. Pasarle el bruto hacia
            # que un match play se resolviese siempre a scratch, por mucho
            # handicap que tuviesen los jugadores.
            team_a_scores = [
                self._net(scores[pid], pid, hole_number, strokes_by_participant)
                for pid in team_a_ids
            ]
            team_b_scores = [
                self._net(scores[pid], pid, hole_number, strokes_by_participant)
                for pid in team_b_ids
            ]
            hole_results.append(
                self._scoring_service.calculate_hole_winner(
                    team_a_scores, team_b_scores, quick_match.match_format
                )
            )

        if not hole_results:
            return None

        standing = self._scoring_service.calculate_match_standing(hole_results)
        return QuickMatchStandingResponseDTO(
            status=standing["status"],
            leading_team=standing["leading_team"],
            holes_played=standing["holes_played"],
            holes_remaining=standing["holes_remaining"],
            is_decided=self._scoring_service.is_match_decided(standing),
        )

    @staticmethod
    def _net(
        gross_score: int,
        participant_id: ParticipantId,
        hole_number: int,
        strokes_by_participant: dict[ParticipantId, ParticipantStrokes],
    ) -> int:
        strokes = strokes_by_participant.get(participant_id)
        if strokes is None:
            return gross_score
        return strokes.net_score(hole_number, gross_score)
