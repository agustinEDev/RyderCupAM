"""
Fourball de torneo con un jugador retirado (Agustín, 24-25 oct 2026).

Si un jugador no se presenta o se va, se le marca como retirado: su bola deja
de contar en los hoyos que no tenía validados y su bando juega con la de su
pareja. Sin esto, con la regla de las cuatro bolas (BE #656) el partido no
avanzaba nunca.

| #   | caso                                                         | esperado                   |
|-----|--------------------------------------------------------------|----------------------------|
| W2  | retirar en fourball, programado o en juego                   | queda retirado             |
| W2b | en individual o foursomes                                    | ValueError                 |
| W2c | con el partido terminado                                     | ValueError                 |
| W2d | alguien que no juega el partido                              | ValueError                 |
| W2e | retirarlo dos veces                                          | ValueError                 |
| W3  | retirar a los dos de un bando                                | ValueError                 |
| W4  | con una tarjeta ya entregada (retirar o deshacer)            | ValueError                 |
| W5  | deshacer                                                     | vuelve a jugar             |
| W5b | deshacer a quien no está retirado                            | ValueError                 |
| W7  | su bola validada antes de retirarse                          | cuenta en ese hoyo         |
| W8  | su bola sin validar                                          | el hoyo se cierra con tres |
| W8b | sin retirados, una bola sin validar                          | el hoyo sigue abierto      |
| W10 | el rival que marcaba el retirado                             | lo marca su pareja         |
| W11 | quien marcaba al retirado                                    | ya no lo marca             |
| W12 | tarjetas: el retirado ni entrega ni hace falta               | terminan los otros tres    |
"""

import pytest

from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat

F = MatchFormat.FOURBALL


def _jugador() -> MatchPlayer:
    return MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        strokes_received=[],
    )


def _partido(formato: MatchFormat = F, *, empezado: bool = True) -> Match:
    por_bando = 1 if formato == MatchFormat.SINGLES else 2
    match = Match.create(
        round_id=RoundId.generate(),
        match_number=1,
        team_a_players=[_jugador() for _ in range(por_bando)],
        team_b_players=[_jugador() for _ in range(por_bando)],
    )
    match.set_marker_assignments(
        ScoringService().generate_marker_assignments(
            match.team_a_players, match.team_b_players, formato
        )
    )
    if empezado:
        match.start()
    return match


def _a1(m: Match) -> UserId:
    return m.team_a_players[0].user_id


def _a2(m: Match) -> UserId:
    return m.team_a_players[1].user_id


def _fila(m: Match, jugador: UserId, team: str, golpes: int | None, validada: bool = True):
    fila = HoleScore.create(
        match_id=m.id, hole_number=1, player_user_id=jugador, team=team, strokes_received=0
    )
    if validada:
        fila.set_own_score(golpes)
        fila.set_marker_score(golpes)
    fila.recalculate_validation()
    return fila


def _hoyo(m: Match, golpes_a1: int | None, *, a1_validada: bool) -> list[HoleScore]:
    """A1 con su bola (o sin validar), A2 hace 5; B1 y B2, 4 y 6."""
    return [
        _fila(m, _a1(m), "A", golpes_a1, validada=a1_validada),
        _fila(m, _a2(m), "A", 5),
        _fila(m, m.team_b_players[0].user_id, "B", 4),
        _fila(m, m.team_b_players[1].user_id, "B", 6),
    ]


class TestRetirar:
    @pytest.mark.parametrize("empezado", [True, False])
    def test_w2_fourball_scheduled_or_in_progress(self, empezado):
        m = _partido(empezado=empezado)
        m.withdraw_player(_a1(m), F)
        assert m.withdrawn_player_ids == (_a1(m),)

    @pytest.mark.parametrize("formato", [MatchFormat.SINGLES, MatchFormat.FOURSOMES])
    def test_w2b_only_in_fourball(self, formato):
        m = _partido(formato)
        with pytest.raises(ValueError):
            m.withdraw_player(_a1(m), formato)
        assert m.withdrawn_player_ids == ()

    def test_w2c_not_once_the_match_is_over(self):
        m = _partido()
        m.complete({"winner": "A", "score": "2&1"})
        with pytest.raises(ValueError):
            m.withdraw_player(_a1(m), F)

    def test_w2d_not_someone_outside_the_match(self):
        m = _partido()
        with pytest.raises(ValueError):
            m.withdraw_player(UserId.generate(), F)

    def test_w2e_not_twice(self):
        m = _partido()
        m.withdraw_player(_a1(m), F)
        with pytest.raises(ValueError):
            m.withdraw_player(_a1(m), F)
        assert m.withdrawn_player_ids == (_a1(m),)

    def test_w3_not_both_players_of_a_side(self):
        m = _partido()
        m.withdraw_player(_a1(m), F)
        with pytest.raises(ValueError):
            m.withdraw_player(_a2(m), F)

    def test_w3b_one_of_each_side_is_fine(self):
        m = _partido()
        m.withdraw_player(_a1(m), F)
        m.withdraw_player(m.team_b_players[0].user_id, F)
        assert len(m.withdrawn_player_ids) == 2

    def test_w4_not_with_a_scorecard_handed_in(self):
        m = _partido()
        m.submit_scorecard(m.team_b_players[0].user_id, F)
        with pytest.raises(ValueError):
            m.withdraw_player(_a1(m), F)

    def test_w4b_undo_neither_with_a_scorecard_handed_in(self):
        m = _partido()
        m.withdraw_player(_a1(m), F)
        m.submit_scorecard(m.team_b_players[0].user_id, F)
        with pytest.raises(ValueError):
            m.reinstate_player(_a1(m))
        assert m.withdrawn_player_ids == (_a1(m),)


class TestDeshacer:
    def test_w5_back_in_play(self):
        m = _partido()
        m.withdraw_player(_a1(m), F)
        m.reinstate_player(_a1(m))
        assert m.withdrawn_player_ids == ()

    def test_w5b_not_someone_who_is_not_withdrawn(self):
        m = _partido()
        with pytest.raises(ValueError):
            m.reinstate_player(_a1(m))


class TestElHoyo:
    def test_w8_his_unvalidated_ball_does_not_hold_the_hole(self):
        m = _partido()
        filas = _hoyo(m, None, a1_validada=False)
        assert ScoringService().hole_result(filas, F, withdrawn=(_a1(m),)) == "B"

    def test_w8b_without_withdrawals_the_hole_stays_open(self):
        m = _partido()
        assert ScoringService().hole_result(_hoyo(m, None, a1_validada=False), F) is None

    def test_w7_his_validated_ball_still_counts(self):
        m = _partido()
        # A1 hizo 3, validado antes de irse: gana A con su bola
        filas = _hoyo(m, 3, a1_validada=True)
        assert ScoringService().hole_result(filas, F, withdrawn=(_a1(m),)) == "A"

    def test_w8c_the_decision_follows_the_same_rule(self):
        m = _partido()
        filas = _hoyo(m, None, a1_validada=False)
        servicio = ScoringService()
        assert servicio.hole_results_by_hole(filas, F, withdrawn=(_a1(m),)) == {1: "B"}
        assert servicio.hole_results_by_hole(filas, F) == {}


class TestMarcadores:
    def test_w10_the_rival_he_marked_is_marked_by_his_partner(self):
        m = _partido()
        a1, a2 = _a1(m), _a2(m)
        rival = next(x.marks_user_id for x in m.marker_assignments if x.scorer_user_id == a1)
        propio = next(x.marks_user_id for x in m.marker_assignments if x.scorer_user_id == a2)
        assert not m.may_mark(a2, rival)

        m.withdraw_player(a1, F)

        assert m.may_mark(a2, rival)
        assert m.may_mark(a2, propio)
        assert not m.may_mark(a1, rival)
        assert {
            x.marks_user_id for x in m.effective_marker_assignments if x.scorer_user_id == a2
        } == {
            rival,
            propio,
        }

    def test_w10b_without_a_draw_the_withdrawn_player_marks_nobody(self):
        """Un partido de antes del sorteo usa la regla de bandos: tampoco marca."""
        m = Match.create(
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[_jugador(), _jugador()],
            team_b_players=[_jugador(), _jugador()],
        )
        m.start()
        rival = m.team_b_players[0].user_id
        assert m.may_mark(_a1(m), rival)

        m.withdraw_player(_a1(m), F)

        assert not m.may_mark(_a1(m), rival)
        assert m.may_mark(_a2(m), rival)

    @pytest.mark.parametrize("quienes", [("A1",), ("A1", "B1"), ("A1", "B2")])
    def test_w10c_who_marks_each_one_points_to_someone_still_playing(self, quienes):
        """
        Revisor sin contexto: `marked_by` seguía apuntando al retirado, y la
        pantalla decía «te marca A1». Cada asignación dice quién marca a su
        anotador, y es quien lo marca de verdad ahora.
        """
        m = _partido()
        ids = {
            "A1": _a1(m),
            "A2": _a2(m),
            "B1": m.team_b_players[0].user_id,
            "B2": m.team_b_players[1].user_id,
        }
        for quien in quienes:
            m.withdraw_player(ids[quien], F)
        retirados = set(m.withdrawn_player_ids)
        efectivas = m.effective_marker_assignments
        quien_le_marca = {a.marks_user_id: a.scorer_user_id for a in efectivas}

        for a in efectivas:
            assert {a.scorer_user_id, a.marks_user_id, a.marked_by_user_id}.isdisjoint(retirados)
            assert a.marked_by_user_id == quien_le_marca[a.scorer_user_id]
        # Todos los que juegan tienen quien les marque
        jugando = set(ids.values()) - retirados
        assert set(quien_le_marca) == jugando

    def test_w11b_without_a_draw_nobody_marks_the_withdrawn_player(self):
        """Revisor sin contexto: con la regla de bandos, un rival aún podía validarle un hoyo."""
        m = Match.create(
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[_jugador(), _jugador()],
            team_b_players=[_jugador(), _jugador()],
        )
        m.start()
        rival = m.team_b_players[0].user_id
        m.withdraw_player(_a1(m), F)

        assert not m.may_mark(rival, _a1(m))
        assert m.may_mark(rival, _a2(m))

    def test_w11_nobody_marks_the_withdrawn_player(self):
        m = _partido()
        a1 = _a1(m)
        m.withdraw_player(a1, F)
        assert all(x.marks_user_id != a1 for x in m.effective_marker_assignments)

    def test_w5c_undoing_restores_the_draw(self):
        m = _partido()
        m.withdraw_player(_a1(m), F)
        m.reinstate_player(_a1(m))
        assert m.effective_marker_assignments == m.marker_assignments


class TestTarjetas:
    def test_w12_the_other_three_finish_the_match(self):
        m = _partido()
        m.withdraw_player(_a1(m), F)
        for jugador in (_a2(m), *[p.user_id for p in m.team_b_players]):
            assert not m.all_scorecards_submitted(F)
            m.submit_scorecard(jugador, F)
        assert m.all_scorecards_submitted(F)

    def test_w12b_the_withdrawn_player_hands_in_nothing(self):
        m = _partido()
        m.withdraw_player(_a1(m), F)
        with pytest.raises(ValueError):
            m.submit_scorecard(_a1(m), F)
