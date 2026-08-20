"""Tests del servicio de dominio hole_completion_service."""

from uuid import uuid4

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.quick_match.domain.services.hole_completion_service import hole_is_complete
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId

A1 = ParticipantId(uuid4())
A2 = ParticipantId(uuid4())
B1 = ParticipantId(uuid4())
B2 = ParticipantId(uuid4())

TEAM_A = {A1, A2}
TEAM_B = {B1, B2}


class TestFoursomes:
    """
    Una bola por bando: el hoyo cuenta cuando cada bando ha entregado la suya,
    la haya anotado cualquiera de los dos companeros.
    """

    def test_one_score_per_side_completes_the_hole(self):
        assert hole_is_complete({A1, B1}, TEAM_A, TEAM_B, MatchFormat.FOURSOMES)

    def test_the_partner_may_be_the_one_who_delivered_the_ball(self):
        assert hole_is_complete({A2, B2}, TEAM_A, TEAM_B, MatchFormat.FOURSOMES)

    def test_a_side_without_its_ball_leaves_the_hole_open(self):
        assert not hole_is_complete({A1, A2}, TEAM_A, TEAM_B, MatchFormat.FOURSOMES)
        assert not hole_is_complete({B1}, TEAM_A, TEAM_B, MatchFormat.FOURSOMES)

    def test_an_empty_hole_is_not_complete(self):
        assert not hole_is_complete(set(), TEAM_A, TEAM_B, MatchFormat.FOURSOMES)

    def test_the_four_scores_also_complete_it(self):
        """Una tarjeta antigua, con los cuatro anotados, sigue valiendo."""
        assert hole_is_complete({A1, A2, B1, B2}, TEAM_A, TEAM_B, MatchFormat.FOURSOMES)


class TestEveryOtherFormat:
    """
    Con una bola por jugador el hoyo necesita las cuatro: en FOURBALL la mejor
    del bando puede cambiar con la que falte.
    """

    def test_fourball_needs_every_participant(self):
        assert hole_is_complete({A1, A2, B1, B2}, TEAM_A, TEAM_B, MatchFormat.FOURBALL)

    def test_fourball_with_a_missing_participant_is_not_complete(self):
        assert not hole_is_complete({A1, A2, B1}, TEAM_A, TEAM_B, MatchFormat.FOURBALL)

    def test_singles_needs_both_players(self):
        assert hole_is_complete({A1, B1}, {A1}, {B1}, MatchFormat.SINGLES)
        assert not hole_is_complete({A1}, {A1}, {B1}, MatchFormat.SINGLES)

    def test_without_a_format_it_falls_back_to_asking_everyone(self):
        """Juego libre: no hay formato, y la regla general es la estricta."""
        assert not hole_is_complete({A1, B1}, TEAM_A, TEAM_B, None)
        assert hole_is_complete({A1, A2, B1, B2}, TEAM_A, TEAM_B, None)


class TestItReadsAMappingToo:
    """
    Los llamadores pasan el dict {participante: golpes} del hoyo, no un set: lo
    que se mira es la pertenencia, y un dict responde igual.
    """

    def test_a_scores_mapping_works_like_the_set(self):
        scores = {A1: 4, B1: 5}

        assert hole_is_complete(scores, TEAM_A, TEAM_B, MatchFormat.FOURSOMES)
        assert not hole_is_complete(scores, TEAM_A, TEAM_B, MatchFormat.FOURBALL)
