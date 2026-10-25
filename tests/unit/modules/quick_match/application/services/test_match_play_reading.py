"""
La lectura completa de un match play rapido: quien gano, el tanteo, cuantos
hoyos cuentan y si se decidio antes de tiempo.

Lo social y el historial necesitan ademas saber si el partido se cerro antes
de quedarse sin hoyos, porque un «3&2» cuenta aunque no llegue al 18.
"""

from uuid import uuid4

from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.services.match_play_result import (
    match_play_reading,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.match_play_scoring import MatchPlayScoring
from src.shared.domain.value_objects.match_format import MatchFormat


def _singles() -> QuickMatch:
    match = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=UserId(uuid4()),
        golf_course_id=GolfCourseId(uuid4()),
        match_format=MatchFormat.SINGLES,
    )
    match.add_participant(QuickMatchParticipant.for_user(UserId(uuid4())))
    return match


def _leer(match, a: dict, b: dict):
    yo, el = (p.participant_id for p in match.participants)
    return match_play_reading(match, {yo: a, el: b}, {}, MatchPlayScoring())


class TestMatchPlayReading:
    def test_decidido_3_y_2(self):
        match = _singles()
        dieciseis = dict.fromkeys(range(1, 17), 4)

        lectura = _leer(match, {**dieciseis, 1: 3, 2: 3, 3: 3}, dieciseis)

        assert (lectura.winner, lectura.score) == ("A", "3&2")
        assert lectura.holes_played == 16
        assert lectura.decided_early is True

    def test_terminado_en_el_18_no_es_antes_de_tiempo(self):
        match = _singles()
        dieciocho = dict.fromkeys(range(1, 19), 4)

        lectura = _leer(match, {**dieciocho, 1: 3}, dieciocho)

        assert (lectura.winner, lectura.score) == ("A", "1UP")
        assert lectura.decided_early is False

    def test_un_hoyo_no_esta_decidido(self):
        match = _singles()

        lectura = _leer(match, {1: 3}, {1: 4})

        assert (lectura.winner, lectura.score, lectura.holes_played) == ("A", "1UP", 1)
        assert lectura.decided_early is False

    def test_sin_hoyos_no_hay_lectura(self):
        match = _singles()

        lectura = _leer(match, {}, {})

        assert (lectura.winner, lectura.score, lectura.holes_played) == (None, None, 0)
        assert lectura.decided_early is False


class TestFourballConLasCuatroBolas:
    """Tambien lo social: el hoyo espera a las cuatro (Agustin, 24 oct 2026)."""

    def _fourball(self):
        match = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=UserId(uuid4()),
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.FOURBALL,
        )
        for team in ("A", "B", "B"):
            match.add_participant(QuickMatchParticipant.for_user(UserId(uuid4()), team=team))
        return match

    def test_con_un_companero_sin_anotar_no_hay_hoyo(self):
        match = self._fourball()
        a1, a2, b1, b2 = (p.participant_id for p in match.participants)
        scores = {a1: {1: 3, 2: 4}, a2: {}, b1: {1: 4, 2: 4}, b2: {1: 4, 2: 4}}

        lectura = match_play_reading(match, scores, {}, MatchPlayScoring())

        assert lectura.holes_played == 0


class TestDecididoEnElOrdenDeLosHoyos:
    """
    Como en los torneos: el partido se decide en el primer hoyo en que la
    ventaja supera a los que quedan, con los anteriores cerrados (Agustin, 25
    oct 2026). Contando sin orden, un fourball con una bola sin anotar en el 4
    salia «Ganado» con un N&M mal calculado.
    """

    def _fourball(self):
        match = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=UserId(uuid4()),
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.FOURBALL,
        )
        for team in ("A", "B", "B"):
            match.add_participant(QuickMatchParticipant.for_user(UserId(uuid4()), team=team))
        return match

    def _gana_a(self, match, hoyos, sin_la_bola_de_a2=()):
        a1, a2, b1, b2 = (p.participant_id for p in match.participants)
        scores = {
            a1: dict.fromkeys(hoyos, 3),
            a2: {h: 4 for h in hoyos if h not in sin_la_bola_de_a2},
            b1: dict.fromkeys(hoyos, 5),
            b2: dict.fromkeys(hoyos, 5),
        }
        return match_play_reading(match, scores, {}, MatchPlayScoring())

    def test_d8_a_missing_ball_before_the_decision_leaves_it_undecided(self):
        lectura = self._gana_a(self._fourball(), range(1, 19), sin_la_bola_de_a2=(4,))

        assert (lectura.winner, lectura.score, lectura.decided_early) == ("A", "17UP", False)

    def test_d10_a_missing_ball_after_the_decision_keeps_10_and_8(self):
        lectura = self._gana_a(self._fourball(), range(1, 13), sin_la_bola_de_a2=(11,))

        assert (lectura.winner, lectura.score) == ("A", "10&8")
        assert lectura.decided_early is True
        # Los que cuentan: hasta la decision, como la pantalla
        assert lectura.holes_played == 10
