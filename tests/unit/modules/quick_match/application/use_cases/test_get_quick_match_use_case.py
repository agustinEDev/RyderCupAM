"""Tests para GetQuickMatchUseCase."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.quick_match.application.dto.quick_match_dto import (
    SubmitHoleScoreRequestDTO,
    SubmitProxyHoleScoreRequestDTO,
)
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchParticipantError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.use_cases.get_quick_match_use_case import (
    GetQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.submit_hole_score_use_case import (
    SubmitQuickMatchHoleScoreUseCase,
)
from src.modules.quick_match.application.use_cases.submit_proxy_hole_score_use_case import (
    SubmitProxyHoleScoreUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.services.scoring_coverage_service import (
    ScoringCoverageService,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.domain.value_objects.scoring_format import ScoringFormat
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.quick_match.conftest import (
    create_golf_course,
    create_user,
    unique_email,
)

pytestmark = pytest.mark.asyncio


async def _create_in_progress_match(qm_uow, creator_id, other_id):
    qm = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creator_id,
        golf_course_id=GolfCourseId(uuid4()),
        match_format=MatchFormat.SINGLES,
    )
    qm.add_participant(QuickMatchParticipant.for_user(other_id))
    qm.start([qm.creator_participant_id])
    async with qm_uow:
        await qm_uow.quick_matches.add(qm)
    return qm


class TestGetQuickMatchUseCase:
    async def test_participant_can_view_detail(self, qm_uow, user_uow, golf_course_uow):
        creator = await create_user(user_uow, "creator@test.com")
        other = await create_user(user_uow, "other@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        use_case = GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        )
        detail = await use_case.execute(str(qm.id.value), str(creator.id.value))

        assert detail.status == "IN_PROGRESS"
        assert detail.hole_scores == []
        assert detail.standing is None
        assert len(detail.scoring_assignments) == 1
        assert detail.scoring_assignments[0].scorer_participant_id == creator.id.value
        assert set(detail.scoring_assignments[0].covered_participant_ids) == {
            creator.id.value,
            other.id.value,
        }

    async def test_non_participant_cannot_view(self, qm_uow, user_uow, golf_course_uow):
        creator = await create_user(user_uow, "creator2@test.com")
        other = await create_user(user_uow, "other2@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        use_case = GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        )
        with pytest.raises(NotQuickMatchParticipantError):
            await use_case.execute(str(qm.id.value), str(UserId(uuid4()).value))

    async def test_not_found_raises(self, qm_uow, user_uow, golf_course_uow):
        use_case = GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        )
        with pytest.raises(QuickMatchNotFoundError):
            await use_case.execute(str(uuid4()), str(uuid4()))

    async def test_standing_computed_after_complete_hole(self, qm_uow, user_uow, golf_course_uow):
        creator = await create_user(user_uow, "creator3@test.com")
        other = await create_user(user_uow, "other3@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        # Solo el creador es anotador: registra su propio score y, por
        # delegacion, el de `other` (que no es anotador en esta partida).
        submit_uc = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        await submit_uc.execute(
            SubmitHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                player_user_id=creator.id.value,
                hole_number=1,
                score=4,
            )
        )
        proxy_uc = SubmitProxyHoleScoreUseCase(qm_uow, ScoringCoverageService())
        await proxy_uc.execute(
            SubmitProxyHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                scorer_user_id=creator.id.value,
                target_participant_id=other.id.value,
                hole_number=1,
                score=5,
            )
        )

        get_uc = GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        )
        detail = await get_uc.execute(str(qm.id.value), str(creator.id.value))

        assert len(detail.hole_scores) == 2
        assert detail.standing is not None
        assert detail.standing.holes_played == 1
        assert detail.standing.leading_team == "A"
        assert detail.standing.status == "1UP"

    async def test_a_raya_loses_the_hole_in_match_play(self, qm_uow, user_uow, golf_course_uow):
        """
        Given un hoyo en el que un jugador recoge la bola y el rival la entrega
        When se calcula el standing
        Then el hoyo es del rival

        Es la regla de match play: quien no acaba el hoyo lo pierde. La raya se
        propaga como None hasta `calculate_hole_winner`, que ya sabe leer un
        bando sin bola porque competicion lo necesitaba.
        """
        creator = await create_user(user_uow, "raya-standing@test.com")
        other = await create_user(user_uow, "raya-standing2@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        submit_uc = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        await submit_uc.execute(
            SubmitHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                player_user_id=creator.id.value,
                hole_number=1,
                score=None,
            )
        )
        proxy_uc = SubmitProxyHoleScoreUseCase(qm_uow, ScoringCoverageService())
        await proxy_uc.execute(
            SubmitProxyHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                scorer_user_id=creator.id.value,
                target_participant_id=other.id.value,
                hole_number=1,
                score=7,
            )
        )

        get_uc = GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        )
        detail = await get_uc.execute(str(qm.id.value), str(creator.id.value))

        assert detail.hole_scores[0].score is None
        assert detail.standing is not None
        assert detail.standing.holes_played == 1
        assert detail.standing.leading_team == "B"
        assert detail.standing.status == "1UP"

    async def test_two_rayas_halve_the_hole(self, qm_uow, user_uow, golf_course_uow):
        """
        Given un hoyo que recogen los dos
        When se calcula el standing
        Then el hoyo queda empatado, no sin jugar
        """
        creator = await create_user(user_uow, "raya-halved@test.com")
        other = await create_user(user_uow, "raya-halved2@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        submit_uc = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        await submit_uc.execute(
            SubmitHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                player_user_id=creator.id.value,
                hole_number=1,
                score=None,
            )
        )
        proxy_uc = SubmitProxyHoleScoreUseCase(qm_uow, ScoringCoverageService())
        await proxy_uc.execute(
            SubmitProxyHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                scorer_user_id=creator.id.value,
                target_participant_id=other.id.value,
                hole_number=1,
                score=None,
            )
        )

        get_uc = GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        )
        detail = await get_uc.execute(str(qm.id.value), str(creator.id.value))

        assert detail.standing is not None
        assert detail.standing.holes_played == 1
        assert detail.standing.leading_team is None

    async def test_registered_participant_handicap_comes_from_user_profile(self, qm_uow, user_uow, golf_course_uow):
        creator = await create_user(user_uow, "creator-hcp@test.com", handicap=12.4)
        other = await create_user(user_uow, "other-hcp@test.com", handicap=None)
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        get_uc = GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        )
        detail = await get_uc.execute(str(qm.id.value), str(creator.id.value))

        creator_dto = next(p for p in detail.participants if p.user_id == creator.id.value)
        other_dto = next(p for p in detail.participants if p.user_id == other.id.value)
        assert creator_dto.handicap == 12.4
        assert other_dto.handicap is None

    async def test_free_play_standing_is_always_none(self, qm_uow, user_uow, golf_course_uow):
        creator = await create_user(user_uow, "creator-freeplay@test.com")
        other = await create_user(user_uow, "other-freeplay@test.com")
        qm = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=creator.id,
            golf_course_id=GolfCourseId(uuid4()),
            scoring_format=ScoringFormat.STABLEFORD,
        )
        qm.add_participant(QuickMatchParticipant.for_user(other.id))
        qm.start([qm.creator_participant_id])
        async with qm_uow:
            await qm_uow.quick_matches.add(qm)

        submit_uc = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        await submit_uc.execute(
            SubmitHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                player_user_id=creator.id.value,
                hole_number=1,
                score=4,
            )
        )

        get_uc = GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        )
        detail = await get_uc.execute(str(qm.id.value), str(creator.id.value))

        assert detail.match_format is None
        assert detail.scoring_format == "STABLEFORD"
        assert detail.standing is None


class TestStandingAppliesHandicap:
    """
    El standing de match play se calcula con scores NETOS.

    Antes se le pasaban los brutos a `calculate_hole_winner`, cuya firma pide
    netos, de modo que un 1 vs 1 se resolvia siempre a scratch por mucho
    handicap que tuviesen los jugadores.
    """

    async def _match_on_real_course(self, qm_uow, golf_course_uow, creator, other, play_mode):
        golf_course = await create_golf_course(golf_course_uow, creator.id)
        qm = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=creator.id,
            golf_course_id=golf_course.id,
            match_format=MatchFormat.SINGLES,
            play_mode=play_mode,
            creator_tee_color=TeeColor.YELLOW,
            creator_tee_gender=Gender.MALE,
        )
        qm.add_participant(
            QuickMatchParticipant.for_user(
                other.id, tee_color=TeeColor.YELLOW, tee_gender=Gender.MALE
            )
        )
        qm.start([qm.creator_participant_id])
        async with qm_uow:
            await qm_uow.quick_matches.add(qm)
        return qm

    async def _score_hole(self, qm_uow, qm, creator, other, hole, creator_score, other_score):
        submit_uc = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        await submit_uc.execute(
            SubmitHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                player_user_id=creator.id.value,
                hole_number=hole,
                score=creator_score,
            )
        )
        proxy_uc = SubmitProxyHoleScoreUseCase(qm_uow, ScoringCoverageService())
        await proxy_uc.execute(
            SubmitProxyHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                scorer_user_id=creator.id.value,
                target_participant_id=other.id.value,
                hole_number=hole,
                score=other_score,
            )
        )

    async def test_higher_handicap_wins_the_hole_thanks_to_the_stroke(
        self, qm_uow, user_uow, golf_course_uow
    ):
        """
        Given un jugador de 5.0 y otro de 20.0 en el hoyo de stroke index 1
        When empatan a golpes brutos
        Then gana el de mas handicap, porque recibe golpe en ese hoyo
        """
        creator = await create_user(user_uow, unique_email("scratch-a"), handicap=5.0)
        other = await create_user(user_uow, unique_email("scratch-b"), handicap=20.0)
        qm = await self._match_on_real_course(
            qm_uow, golf_course_uow, creator, other, PlayMode.HANDICAP
        )

        # Hoyo 1 = stroke index 1 en el campo de prueba. Empate a 5 golpes brutos.
        await self._score_hole(qm_uow, qm, creator, other, hole=1, creator_score=5, other_score=5)

        get_uc = GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        )
        detail = await get_uc.execute(str(qm.id.value), str(creator.id.value))

        assert detail.standing is not None
        assert detail.standing.leading_team == "B"
        assert detail.standing.status == "1UP"

    async def test_scratch_mode_ignores_the_handicap(self, qm_uow, user_uow, golf_course_uow):
        """
        Given la misma pareja y el mismo empate bruto, pero la partida en SCRATCH
        When se calcula el standing
        Then el hoyo queda empatado: nadie recibe golpes
        """
        creator = await create_user(user_uow, unique_email("scratch-c"), handicap=5.0)
        other = await create_user(user_uow, unique_email("scratch-d"), handicap=20.0)
        qm = await self._match_on_real_course(
            qm_uow, golf_course_uow, creator, other, PlayMode.SCRATCH
        )

        await self._score_hole(qm_uow, qm, creator, other, hole=1, creator_score=5, other_score=5)

        get_uc = GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        )
        detail = await get_uc.execute(str(qm.id.value), str(creator.id.value))

        assert detail.standing is not None
        assert detail.standing.leading_team is None
        assert detail.play_mode == "SCRATCH"
        assert all(ps.strokes_by_hole == {} for ps in detail.participant_strokes)

    async def test_detail_exposes_the_strokes_used_to_decide_the_holes(
        self, qm_uow, user_uow, golf_course_uow
    ):
        """La tarjeta debe pintar los mismos golpes que han decidido los hoyos."""
        creator = await create_user(user_uow, unique_email("scratch-e"), handicap=5.0)
        other = await create_user(user_uow, unique_email("scratch-f"), handicap=20.0)
        qm = await self._match_on_real_course(
            qm_uow, golf_course_uow, creator, other, PlayMode.HANDICAP
        )

        get_uc = GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        )
        detail = await get_uc.execute(str(qm.id.value), str(creator.id.value))

        by_participant = {ps.participant_id: ps for ps in detail.participant_strokes}
        creator_strokes = by_participant[creator.id.value]
        other_strokes = by_participant[other.id.value]

        # Reparto diferencial: solo recibe el de mas handicap
        assert creator_strokes.strokes_by_hole == {}
        assert other_strokes.strokes_by_hole
        # Y recibe en los hoyos mas dificiles: el campo de prueba tiene SI = numero de hoyo
        assert min(other_strokes.strokes_by_hole) == 1


async def _create_team_match(qm_uow, match_format, creator_id, partner_id, rival_ids):
    """Partida 2v2 en marcha: el creador queda en el bando A y anota para todos."""
    qm = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creator_id,
        golf_course_id=GolfCourseId(uuid4()),
        match_format=match_format,
    )
    qm.add_participant(QuickMatchParticipant.for_user(partner_id, team="A"))
    for rival_id in rival_ids:
        qm.add_participant(QuickMatchParticipant.for_user(rival_id, team="B"))
    qm.start([qm.creator_participant_id])
    async with qm_uow:
        await qm_uow.quick_matches.add(qm)
    return qm


async def _score(qm_uow, qm, scorer_id, player_id, hole_number, score):
    """Anota un golpe: propio si el jugador es el anotador, delegado si no."""
    if player_id == scorer_id:
        await SubmitQuickMatchHoleScoreUseCase(qm_uow).execute(
            SubmitHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                player_user_id=player_id.value,
                hole_number=hole_number,
                score=score,
            )
        )
        return
    await SubmitProxyHoleScoreUseCase(qm_uow, ScoringCoverageService()).execute(
        SubmitProxyHoleScoreRequestDTO(
            quick_match_id=qm.id.value,
            scorer_user_id=scorer_id.value,
            target_participant_id=player_id.value,
            hole_number=hole_number,
            score=score,
        )
    )


class TestFoursomesScoresOneBallPerSide:
    """
    FOURSOMES se juega a golpes alternos con UNA bola por bando.

    El filtro del standing exigia los cuatro scores por hoyo, asi que una tarjeta
    llevada como se juega —cada hoyo anotado por quien golpeo— no puntuaba ni un
    solo hoyo y el partido se quedaba sin resultado.
    """

    async def _players(self, user_uow, tag):
        return [
            await create_user(user_uow, unique_email(f"{tag}-{i}")) for i in range(4)
        ]

    async def test_hole_counts_with_one_score_per_side(self, qm_uow, user_uow, golf_course_uow):
        creator, partner, rival_a, rival_b = await self._players(user_uow, "foursomes-ok")
        qm = await _create_team_match(
            qm_uow, MatchFormat.FOURSOMES, creator.id, partner.id, [rival_a.id, rival_b.id]
        )

        # Una bola por bando: la del bando A la anota el creador, la del B un rival.
        await _score(qm_uow, qm, creator.id, creator.id, 1, 4)
        await _score(qm_uow, qm, creator.id, rival_a.id, 1, 5)

        detail = await GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        ).execute(str(qm.id.value), str(creator.id.value))

        assert detail.standing is not None
        assert detail.standing.holes_played == 1
        assert detail.standing.leading_team == "A"
        assert detail.standing.status == "1UP"

    async def test_the_partner_may_be_the_one_who_enters_it(self, qm_uow, user_uow, golf_course_uow):
        creator, partner, rival_a, rival_b = await self._players(user_uow, "foursomes-partner")
        qm = await _create_team_match(
            qm_uow, MatchFormat.FOURSOMES, creator.id, partner.id, [rival_a.id, rival_b.id]
        )

        # La bola del bando A entra a nombre del companero, no del creador: el
        # golpe es del bando y lo anota cualquiera de los dos.
        await _score(qm_uow, qm, creator.id, partner.id, 1, 4)
        await _score(qm_uow, qm, creator.id, rival_b.id, 1, 6)

        detail = await GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        ).execute(str(qm.id.value), str(creator.id.value))

        assert detail.standing is not None
        assert detail.standing.holes_played == 1
        assert detail.standing.leading_team == "A"

    async def test_hole_still_needs_both_sides(self, qm_uow, user_uow, golf_course_uow):
        creator, partner, rival_a, rival_b = await self._players(user_uow, "foursomes-half")
        qm = await _create_team_match(
            qm_uow, MatchFormat.FOURSOMES, creator.id, partner.id, [rival_a.id, rival_b.id]
        )

        # Solo el bando A ha entregado: no hay hoyo que comparar.
        await _score(qm_uow, qm, creator.id, creator.id, 1, 4)

        detail = await GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        ).execute(str(qm.id.value), str(creator.id.value))

        assert detail.standing is None

    async def test_fourball_still_requires_every_player(self, qm_uow, user_uow, golf_course_uow):
        creator, partner, rival_a, rival_b = await self._players(user_uow, "fourball-strict")
        qm = await _create_team_match(
            qm_uow, MatchFormat.FOURBALL, creator.id, partner.id, [rival_a.id, rival_b.id]
        )

        # FOURBALL si tiene dos bolas por bando: con una sin anotar, la mejor del
        # bando aun puede cambiar, asi que el hoyo no cuenta.
        await _score(qm_uow, qm, creator.id, creator.id, 1, 4)
        await _score(qm_uow, qm, creator.id, rival_a.id, 1, 5)
        await _score(qm_uow, qm, creator.id, rival_b.id, 1, 6)

        detail = await GetQuickMatchUseCase(
            qm_uow, user_uow, ScoringService(), ScoringCoverageService(), golf_course_uow
        ).execute(str(qm.id.value), str(creator.id.value))

        assert detail.standing is None
