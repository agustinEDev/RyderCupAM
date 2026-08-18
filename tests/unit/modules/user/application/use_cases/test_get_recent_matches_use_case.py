"""
Tests del historial de partidas de un jugador (BE #128).

El feed mete en una misma lista dos cosas que no se parecen: un partido de
torneo, que se juega por hoyos contra un rival y acaba en "3&2", y una partida
rápida libre, que se juega contra el par y acaba en "+18" o en puntos. Estos
tests fijan qué campos rellena cada una y, sobre todo, cuáles deja en None en
lugar de inventar una equivalencia.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryCompetitionUnitOfWork,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.domain.value_objects.scoring_format import ScoringFormat
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_unit_of_work import (
    InMemoryQuickMatchUnitOfWork,
)
from src.modules.user.application.use_cases.get_recent_matches_use_case import (
    GetRecentMatchesUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

HOLES = range(1, 19)


@pytest.fixture
def competition_uow():
    return InMemoryCompetitionUnitOfWork()


@pytest.fixture
def qm_uow():
    return InMemoryQuickMatchUnitOfWork()


@pytest.fixture
def golf_course_uow():
    return InMemoryGolfCourseUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


def unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}@test.com"


async def create_user(user_uow, first_name: str, handicap: float | None = None):
    user = User.create(
        first_name=first_name,
        last_name="Player",
        email_str=unique_email(first_name.lower()),
        plain_password="SecureP@ssw0rd123",
    )
    if handicap is not None:
        user.update_handicap(handicap)
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def create_golf_course(golf_course_uow, creator_id, name: str = "Test Golf Club"):
    """Campo de par 72: 18 hoyos de par 4, stroke index 1 a 18."""
    tees = [
        Tee(
            color=TeeColor.YELLOW,
            gender=Gender.MALE,
            identifier="Yellow",
            course_rating=70.0,
            slope_rating=125,
        ),
        Tee(
            color=TeeColor.WHITE,
            gender=Gender.MALE,
            identifier="White",
            course_rating=72.0,
            slope_rating=130,
        ),
    ]
    golf_course = GolfCourse.create(
        name=name,
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=tees,
        holes=[Hole(number=i, par=4, stroke_index=i) for i in HOLES],
    )
    golf_course.approve()
    async with golf_course_uow:
        await golf_course_uow.golf_courses.save(golf_course)
    return golf_course


def _use_case(user_uow, competition_uow, qm_uow, golf_course_uow):
    return GetRecentMatchesUseCase(
        user_uow=user_uow,
        competition_uow=competition_uow,
        quick_match_uow=qm_uow,
        golf_course_uow=golf_course_uow,
    )


async def played_quick_match(
    qm_uow,
    golf_course,
    creator,
    *,
    scoring_format: ScoringFormat | None = ScoringFormat.MEDAL,
    match_format: MatchFormat | None = None,
    others=(),
    strokes_by_participant_index: dict[int, int] | None = None,
    strokes_per_hole: int = 4,
    holes_played: int = 18,
    creator_tee_color: TeeColor | None = None,
    creator_tee_gender: Gender | None = None,
):
    """
    Una partida rápida terminada con la vuelta anotada.

    `strokes_by_participant_index` permite dar golpes distintos a cada
    participante por su posición en el roster (0 = creador); sin él todos
    firman los mismos. `holes_played` deja la vuelta a medias, que es como
    acaba un match play que se cierra antes del 18.
    """
    match = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creator.id,
        golf_course_id=golf_course.id,
        match_format=match_format,
        scoring_format=scoring_format,
        creator_tee_color=creator_tee_color,
        creator_tee_gender=creator_tee_gender,
    )
    for participant in others:
        match.add_participant(participant)

    participant_ids = [p.participant_id for p in match.participants]
    match.start(scorer_ids=[participant_ids[0]])
    match.complete()

    async with qm_uow:
        await qm_uow.quick_matches.add(match)
        for index, participant_id in enumerate(participant_ids):
            strokes = (strokes_by_participant_index or {}).get(index, strokes_per_hole)
            for hole_number in range(1, holes_played + 1):
                await qm_uow.quick_match_hole_scores.add(
                    QuickMatchHoleScore(
                        id=QuickMatchHoleScoreId.generate(),
                        quick_match_id=match.id,
                        hole_number=hole_number,
                        participant_id=participant_id,
                        score=strokes,
                        recorded_by_participant_id=participant_ids[0],
                    )
                )
        await qm_uow.commit()

    return match


async def played_competition_match(
    competition_uow,
    golf_course,
    *,
    team_a_user_ids,
    team_b_user_ids,
    round_date: date,
    result: dict,
    match_format: MatchFormat = MatchFormat.SINGLES,
):
    """Un partido de torneo terminado, con su ronda y su competición."""
    creator_id = team_a_user_ids[0]
    competition = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creator_id,
        name=CompetitionName("Ryder Cup Test"),
        dates=DateRange(start_date=round_date, end_date=round_date + timedelta(days=2)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_1_name="Team A",
        team_2_name="Team B",
        team_assignment=TeamAssignment.MANUAL,
    )
    round_ = Round.create(
        competition_id=competition.id,
        golf_course_id=golf_course.id,
        round_date=round_date,
        session_type=SessionType.MORNING,
        match_format=match_format,
    )

    def player(user_id):
        return MatchPlayer(
            user_id=user_id,
            playing_handicap=10,
            tee_color=TeeColor.YELLOW,
            tee_gender=Gender.MALE,
            strokes_received=tuple(range(1, 11)),
        )

    match = Match.create(
        round_id=round_.id,
        match_number=1,
        team_a_players=[player(uid) for uid in team_a_user_ids],
        team_b_players=[player(uid) for uid in team_b_user_ids],
    )
    match.start()
    match.complete(result)

    async with competition_uow:
        await competition_uow.competitions.add(competition)
        await competition_uow.rounds.add(round_)
        await competition_uow.matches.add(match)
        await competition_uow.commit()

    return match


@pytest.mark.asyncio
class TestEmptyHistory:
    """Una cuenta sin historial devuelve una lista vacía, no un error."""

    async def test_new_account_has_no_matches(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        user = await create_user(user_uow, "Empty")

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(user.id)

        assert feed.matches == []


@pytest.mark.asyncio
class TestFreePlayQuickMatch:
    """Partido libre: se juega contra el par, no contra un rival."""

    async def test_medal_reports_net_strokes_against_par(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Par 72, jugador scratch, 5 golpes por hoyo: +18, no los 90 brutos."""
        user = await create_user(user_uow, "Medal", handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await played_quick_match(qm_uow, course, user, strokes_per_hole=5)

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(user.id)

        entry = feed.matches[0]
        assert entry.score == "+18"
        assert entry.scoring_format == "MEDAL"
        assert entry.match_format is None
        # Los puntos se calculan en cualquier formato: son la unica cifra que
        # compara vueltas entre si, porque 36 es jugar a tu handicap. Un
        # scratch con bogey en cada hoyo firma 18
        assert entry.stableford_points == 18
        assert entry.total_strokes == 90
        assert entry.holes_played == 18

    async def test_stableford_reports_points(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Scratch en par 72 firmando el par: 2 puntos por hoyo, 36 en total."""
        user = await create_user(user_uow, "Stable", handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await played_quick_match(
            qm_uow, course, user, scoring_format=ScoringFormat.STABLEFORD, strokes_per_hole=4
        )

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(user.id)

        entry = feed.matches[0]
        assert entry.stableford_points == 36
        assert entry.score == "36 pts"

    async def test_has_no_match_play_result(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """WON/LOST es de match play: en partido libre no hay a quién ganarle."""
        user = await create_user(user_uow, "NoResult", handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await played_quick_match(qm_uow, course, user)

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(user.id)

        assert feed.matches[0].result is None

    async def test_the_others_are_rivals_not_partners(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Sin bandos, la clasificación es individual: nadie es compañero."""
        user = await create_user(user_uow, "Solo", handicap=0)
        rival = await create_user(user_uow, "Rival", handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await played_quick_match(
            qm_uow, course, user, others=[QuickMatchParticipant.for_user(rival.id)]
        )

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(user.id)

        assert feed.matches[0].partners == []
        assert feed.matches[0].opponents == ["Rival Player"]

    async def test_a_guest_shows_the_name_typed_in_the_match(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """El invitado no tiene perfil: su nombre vive dentro de la partida."""
        user = await create_user(user_uow, "Host", handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await played_quick_match(
            qm_uow,
            course,
            user,
            others=[QuickMatchParticipant.for_guest("Seve", "Ballesteros", handicap=0)],
        )

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(user.id)

        assert feed.matches[0].opponents == ["Seve Ballesteros"]

    async def test_reports_the_golf_course_played(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        user = await create_user(user_uow, "Course", handicap=0)
        course = await create_golf_course(golf_course_uow, user.id, name="Valderrama")
        await played_quick_match(qm_uow, course, user)

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(user.id)

        assert feed.matches[0].golf_course_name == "Valderrama"
        assert feed.matches[0].golf_course_id == str(course.id.value)


@pytest.mark.asyncio
class TestTeamQuickMatch:
    """Partida rápida por equipos: sí se juega por hoyos contra un rival."""

    async def test_winner_gets_won_and_the_loser_the_same_score(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        SINGLES, el creador firma 4 y el rival 5 en los 18 hoyos: los gana todos.
        Con la vuelta entera anotada la ventaja es de 18 y no quedan hoyos, así
        que el resultado es "18UP" para los dos, con el signo cambiado.
        """
        winner = await create_user(user_uow, "Winner", handicap=0)
        loser = await create_user(user_uow, "Loser", handicap=0)
        course = await create_golf_course(golf_course_uow, winner.id)
        await played_quick_match(
            qm_uow,
            course,
            winner,
            scoring_format=None,
            match_format=MatchFormat.SINGLES,
            others=[QuickMatchParticipant.for_user(loser.id)],
            strokes_by_participant_index={0: 4, 1: 5},
        )

        use_case = _use_case(user_uow, competition_uow, qm_uow, golf_course_uow)

        won = (await use_case.execute(winner.id)).matches[0]
        lost = (await use_case.execute(loser.id)).matches[0]

        assert won.result == "WON"
        assert lost.result == "LOST"
        assert won.score == lost.score == "18UP"

    async def test_a_match_closed_early_reports_the_holes_that_were_left(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Diez hoyos anotados y ganados todos: 10 de ventaja con 8 por jugar. Eso
        se escribe "10&8", la notación de un match play que no llega al 18.
        """
        winner = await create_user(user_uow, "Early", handicap=0)
        loser = await create_user(user_uow, "Late", handicap=0)
        course = await create_golf_course(golf_course_uow, winner.id)
        await played_quick_match(
            qm_uow,
            course,
            winner,
            scoring_format=None,
            match_format=MatchFormat.SINGLES,
            others=[QuickMatchParticipant.for_user(loser.id)],
            strokes_by_participant_index={0: 4, 1: 5},
            holes_played=10,
        )

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            winner.id
        )

        assert feed.matches[0].score == "10&8"
        assert feed.matches[0].result == "WON"

    async def test_all_holes_halved_ends_as_halved(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Nunca se decide: el resultado es la ventaja real (ninguna), no un "N&M"."""
        one = await create_user(user_uow, "One", handicap=0)
        two = await create_user(user_uow, "Two", handicap=0)
        course = await create_golf_course(golf_course_uow, one.id)
        await played_quick_match(
            qm_uow,
            course,
            one,
            scoring_format=None,
            match_format=MatchFormat.SINGLES,
            others=[QuickMatchParticipant.for_user(two.id)],
            strokes_per_hole=4,
        )

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(one.id)

        assert feed.matches[0].result == "HALVED"
        assert feed.matches[0].score == "AS"

    async def test_the_rival_is_an_opponent(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        one = await create_user(user_uow, "One", handicap=0)
        two = await create_user(user_uow, "Two", handicap=0)
        course = await create_golf_course(golf_course_uow, one.id)
        await played_quick_match(
            qm_uow,
            course,
            one,
            scoring_format=None,
            match_format=MatchFormat.SINGLES,
            others=[QuickMatchParticipant.for_user(two.id)],
        )

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(one.id)

        assert feed.matches[0].opponents == ["Two Player"]
        assert feed.matches[0].partners == []


@pytest.mark.asyncio
class TestCompetitionMatch:
    """Partido de torneo: fecha, campo y nombre del torneo salen de la ronda."""

    async def test_reports_tournament_date_and_result_from_the_player_side(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        player = await create_user(user_uow, "Home")
        rival = await create_user(user_uow, "Away")
        course = await create_golf_course(golf_course_uow, player.id, name="Real Club")
        await played_competition_match(
            competition_uow,
            course,
            team_a_user_ids=[player.id],
            team_b_user_ids=[rival.id],
            round_date=date(2026, 6, 1),
            result={"winner": "B", "score": "3&2"},
        )

        use_case = _use_case(user_uow, competition_uow, qm_uow, golf_course_uow)

        home = (await use_case.execute(player.id)).matches[0]
        away = (await use_case.execute(rival.id)).matches[0]

        assert home.date == date(2026, 6, 1)
        assert home.tournament_name == "Ryder Cup Test"
        assert home.golf_course_name == "Real Club"
        assert home.match_format == "SINGLES"
        assert home.score == "3&2"
        assert home.result == "LOST"
        assert away.result == "WON"

    async def test_has_no_scoring_format(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """MEDAL/STABLEFORD es el eje de las partidas rápidas; aquí no aplica."""
        player = await create_user(user_uow, "Home")
        rival = await create_user(user_uow, "Away")
        course = await create_golf_course(golf_course_uow, player.id)
        await played_competition_match(
            competition_uow,
            course,
            team_a_user_ids=[player.id],
            team_b_user_ids=[rival.id],
            round_date=date(2026, 6, 1),
            result={"winner": "A", "score": "2UP"},
        )

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert feed.matches[0].scoring_format is None
        assert feed.matches[0].stableford_points is None

    async def test_separates_partners_from_opponents_in_fourball(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        player = await create_user(user_uow, "Home")
        partner = await create_user(user_uow, "Partner")
        rival_one = await create_user(user_uow, "Rivalone")
        rival_two = await create_user(user_uow, "Rivaltwo")
        course = await create_golf_course(golf_course_uow, player.id)
        await played_competition_match(
            competition_uow,
            course,
            team_a_user_ids=[player.id, partner.id],
            team_b_user_ids=[rival_one.id, rival_two.id],
            round_date=date(2026, 6, 1),
            result={"winner": "A", "score": "2UP"},
            match_format=MatchFormat.FOURBALL,
        )

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert feed.matches[0].partners == ["Partner Player"]
        assert sorted(feed.matches[0].opponents) == ["Rivalone Player", "Rivaltwo Player"]


@pytest.mark.asyncio
class TestFeedOrderAndLimit:
    """El feed mezcla ambas fuentes en una única lista ordenada."""

    async def test_most_recent_first_across_both_sources(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        La partida rápida se fecha hoy y el torneo en 2026-06-01: la rápida va
        primero aunque venga de la otra fuente.
        """
        player = await create_user(user_uow, "Mixed", handicap=0)
        rival = await create_user(user_uow, "Away")
        course = await create_golf_course(golf_course_uow, player.id)
        await played_competition_match(
            competition_uow,
            course,
            team_a_user_ids=[player.id],
            team_b_user_ids=[rival.id],
            round_date=date(2026, 6, 1),
            result={"winner": "A", "score": "2UP"},
        )
        await played_quick_match(qm_uow, course, player)

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert len(feed.matches) == 2
        assert feed.matches[0].tournament_name is None
        assert feed.matches[1].tournament_name == "Ryder Cup Test"

    async def test_limit_applies_after_merging_both_sources(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Recortar antes de mezclar dejaría fuera partidas más recientes de una
        fuente por culpa de las de la otra.
        """
        player = await create_user(user_uow, "Limited", handicap=0)
        rival = await create_user(user_uow, "Away")
        course = await create_golf_course(golf_course_uow, player.id)
        await played_competition_match(
            competition_uow,
            course,
            team_a_user_ids=[player.id],
            team_b_user_ids=[rival.id],
            round_date=date(2026, 6, 1),
            result={"winner": "A", "score": "2UP"},
        )
        await played_quick_match(qm_uow, course, player)

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id, limit=1
        )

        assert len(feed.matches) == 1
        assert feed.matches[0].tournament_name is None


@pytest.mark.asyncio
class TestHiddenMatches:
    """Regla de #127: ocultar es por persona, no por partida."""

    async def test_a_hidden_match_leaves_the_feed_of_whoever_hid_it(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        hider = await create_user(user_uow, "Hider", handicap=0)
        other = await create_user(user_uow, "Other", handicap=0)
        course = await create_golf_course(golf_course_uow, hider.id)
        match = await played_quick_match(
            qm_uow, course, hider, others=[QuickMatchParticipant.for_user(other.id)]
        )

        async with qm_uow:
            stored = await qm_uow.quick_matches.find_by_id(match.id)
            stored.hide_for(stored.participants[0].participant_id)
            await qm_uow.quick_matches.update(stored)
            await qm_uow.commit()

        use_case = _use_case(user_uow, competition_uow, qm_uow, golf_course_uow)

        assert (await use_case.execute(hider.id)).matches == []
        assert len((await use_case.execute(other.id)).matches) == 1


@pytest.mark.asyncio
class TestComparableFigures:
    """
    Golpes, hoyos y puntos Stableford en cualquier formato (FE #306).

    El historial mezclaba notaciones que no se pueden comparar entre sí —"1UP"
    de match play, "+18" de medal, "26 pts" de Stableford— y obligaba a
    traducir mentalmente antes de saber qué vuelta fue mejor. Los puntos son la
    vara común: 36 es jugar a tu hándicap, en cualquier campo y formato.
    """

    async def test_a_match_play_round_also_reports_strokes_and_points(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        player = await create_user(user_uow, "Matchplay", handicap=0)
        rival = await create_user(user_uow, "Rival", handicap=0)
        course = await create_golf_course(golf_course_uow, player.id)
        await played_quick_match(
            qm_uow,
            course,
            player,
            scoring_format=None,
            match_format=MatchFormat.SINGLES,
            others=[QuickMatchParticipant.for_user(rival.id)],
            strokes_by_participant_index={0: 5, 1: 6},
        )

        entry = (
            await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(player.id)
        ).matches[0]
        # Bogey en cada hoyo para un scratch: 90 golpes y 18 puntos
        assert entry.total_strokes == 90
        assert entry.holes_played == 18
        assert entry.stableford_points == 18
        # El resultado del match play no se pierde, solo deja de ser lo único
        assert entry.result == "WON"

    async def test_half_a_round_reports_the_holes_it_was_played_over(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Sin este dato, "45 golpes" al lado de "90 golpes" parece un juegazo en
        vez de media vuelta.
        """
        player = await create_user(user_uow, "Halfround", handicap=0)
        course = await create_golf_course(golf_course_uow, player.id)
        await played_quick_match(qm_uow, course, player, strokes_per_hole=5, holes_played=9)

        entry = (
            await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(player.id)
        ).matches[0]
        assert entry.holes_played == 9
        assert entry.total_strokes == 45
        assert entry.stableford_points == 9


class TestParPorBarra:
    """
    Los puntos se cuentan contra el par de la barra que se juega.

    `reference_card` es la tarjeta derivada de la primera salida. En 25 de los
    800 campos federados el par cambia de una barra a otra —normalmente el hoyo
    que las mujeres juegan como par 5 y los hombres como par 4—, así que
    puntuar a todos contra la de referencia le cuenta a quien juega otra barra
    un birdie como par.
    """

    @staticmethod
    async def _course_with_longer_red(golf_course_uow, creator_id):
        """Rojas juegan par 5 los hoyos 1 y 2; la tarjeta del campo, par 4."""
        red_holes = [
            Hole(number=i, par=5 if i in (1, 2) else 4, stroke_index=i) for i in HOLES
        ]
        tees = [
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier="Yellow",
                course_rating=70.0,
                slope_rating=125,
                holes=[Hole(number=i, par=4, stroke_index=i) for i in HOLES],
            ),
            Tee(
                color=TeeColor.RED,
                gender=Gender.FEMALE,
                identifier="Red",
                course_rating=72.0,
                slope_rating=130,
                holes=red_holes,
            ),
        ]
        course = GolfCourse.create(
            name="Two Cards Club",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees,
            holes=[Hole(number=i, par=4, stroke_index=i) for i in HOLES],
        )
        course.approve()
        async with golf_course_uow:
            await golf_course_uow.golf_courses.save(course)
        return course

    @pytest.mark.asyncio
    async def test_los_puntos_salen_contra_el_par_de_su_barra(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Scratch de rojas firmando 4 en todos los hoyos.

        Contra su tarjeta son dos birdies (hoyos 1 y 2, par 5) y dieciséis
        pares: 3 + 3 + 16 x 2 = 38 puntos. Contra la del campo serían 36, que es
        lo que salía antes.
        """
        user = await create_user(user_uow, "Roja", handicap=0)
        course = await self._course_with_longer_red(golf_course_uow, user.id)
        await played_quick_match(
            qm_uow,
            course,
            user,
            scoring_format=ScoringFormat.STABLEFORD,
            strokes_per_hole=4,
            creator_tee_color=TeeColor.RED,
            creator_tee_gender=Gender.FEMALE,
        )

        feed = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(user.id)

        assert feed.matches[0].stableford_points == 38
