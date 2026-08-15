"""
Tests del StrokeAllocationService — reparto de golpes en partida rapida.

El caso que abre el fichero es real: la partida "Prueba" en Golf de Meis que
destapo el fallo. Un jugador de 18 salia recibiendo 31 golpes y su rival de 20.7
solo 27, y ademas el resultado se decidia a golpes brutos. Los numeros de ese
test son los del campo federado, no inventados.
"""

from decimal import Decimal

import pytest

from src.modules.competition.domain.services.playing_handicap_calculator import TeeRating
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.quick_match.domain.services.stroke_allocation_service import (
    StrokeAllocationService,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.shared.domain.value_objects.gender import Gender

# Golf de Meis (RFEG id 487), recorrido Par 72. Amarillas valoradas por genero.
MEIS_AMARILLAS_M = TeeRating(course_rating=Decimal("73.1"), slope_rating=140, par=72)
MEIS_AMARILLAS_F = TeeRating(course_rating=Decimal("79.4"), slope_rating=147, par=72)

# Stroke index reales de Meis, hoyo 1..18
MEIS_STROKE_INDEX = [7, 1, 13, 5, 15, 9, 3, 11, 17, 16, 2, 14, 12, 8, 18, 6, 4, 10]


def _holes_by_stroke_index(stroke_index_by_hole: list[int] | None = None) -> list[int]:
    """Numeros de hoyo ordenados del mas dificil (SI 1) al mas facil (SI 18)."""
    stroke_index_by_hole = stroke_index_by_hole or list(range(1, 19))
    holes = list(range(1, len(stroke_index_by_hole) + 1))
    return sorted(holes, key=lambda h: stroke_index_by_hole[h - 1])


def _guest(name: str, handicap: float, color: TeeColor, gender: Gender | None, team=None):
    return QuickMatchParticipant(
        participant_id=ParticipantId.generate(),
        user_id=None,
        first_name=name,
        last_name="Test",
        handicap=handicap,
        team=team,
        tee_color=color,
        tee_gender=gender,
    )


@pytest.fixture
def service() -> StrokeAllocationService:
    return StrokeAllocationService()


class TestSinglesMeisRegression:
    """El caso real que destapo el fallo (partida 'Prueba', Golf de Meis)."""

    def test_singles_gives_strokes_only_to_the_higher_handicap(self, service):
        """
        Given un 18.0 y un 20.7, ambos desde Amarillas masculino de Meis
        When se reparte el handicap del match play
        Then solo recibe el de 20.7, y recibe la diferencia (4 golpes)
        """
        me = _guest("Agustin", 18.0, TeeColor.YELLOW, Gender.MALE)
        rival = _guest("Alberto", 20.7, TeeColor.YELLOW, Gender.MALE)

        result = service.allocate(
            participants=[me, rival],
            handicaps={
                me.participant_id: Decimal("18.0"),
                rival.participant_id: Decimal("20.7"),
            },
            tee_ratings={("YELLOW", "MALE"): MEIS_AMARILLAS_M},
            holes_by_stroke_index=_holes_by_stroke_index(MEIS_STROKE_INDEX),
            match_format=MatchFormat.SINGLES,
            allowance_percentage=100,
            play_mode=PlayMode.HANDICAP,
        )

        # Playing Handicaps individuales: 18.0 -> 23, 20.7 -> 27
        assert result[me.participant_id].playing_handicap == 23
        assert result[rival.participant_id].playing_handicap == 27

        # Pero el reparto es diferencial: el de menos PH juega off scratch
        assert result[me.participant_id].strokes_received == ()
        # 27 - 23 = 4 golpes, en los hoyos de SI 1, 2, 3 y 4 -> hoyos 2, 11, 7 y 17
        assert sorted(result[rival.participant_id].strokes_received) == [2, 7, 11, 17]

    def test_lower_handicap_never_receives_more_than_the_higher_one(self, service):
        """
        Given el 18.0 desde la barra femenina y el 20.7 desde la masculina
        When se reparte el handicap
        Then el reparto sigue al Playing Handicap, no al Handicap Index

        Es el escenario exacto de la captura: la barra femenina de Meis esta
        valorada 6.3 de CR y 7 de slope por encima de la masculina, asi que el
        18.0 saca mas Playing Handicap. Lo que el reparto diferencial garantiza
        es que solo uno de los dos recibe, nunca los dos a la vez.
        """
        me = _guest("Agustin", 18.0, TeeColor.YELLOW, Gender.FEMALE)
        rival = _guest("Alberto", 20.7, TeeColor.YELLOW, Gender.MALE)

        result = service.allocate(
            participants=[me, rival],
            handicaps={
                me.participant_id: Decimal("18.0"),
                rival.participant_id: Decimal("20.7"),
            },
            tee_ratings={
                ("YELLOW", "MALE"): MEIS_AMARILLAS_M,
                ("YELLOW", "FEMALE"): MEIS_AMARILLAS_F,
            },
            holes_by_stroke_index=_holes_by_stroke_index(MEIS_STROKE_INDEX),
            match_format=MatchFormat.SINGLES,
            allowance_percentage=100,
            play_mode=PlayMode.HANDICAP,
        )

        assert result[me.participant_id].playing_handicap == 31
        assert result[rival.participant_id].playing_handicap == 27

        # Uno de los dos recibe; el otro, nada. Nunca los dos.
        assert result[rival.participant_id].strokes_received == ()
        assert len(result[me.participant_id].strokes_received) == 4


class TestScratch:
    """SCRATCH no reparte nada, en ningun formato."""

    @pytest.mark.parametrize(
        "match_format",
        [MatchFormat.SINGLES, MatchFormat.FOURBALL, MatchFormat.FOURSOMES, None],
    )
    def test_scratch_gives_nobody_strokes(self, service, match_format):
        a = _guest("A", 5.0, TeeColor.YELLOW, Gender.MALE, team="A")
        b = _guest("B", 30.0, TeeColor.YELLOW, Gender.MALE, team="B")

        result = service.allocate(
            participants=[a, b],
            handicaps={a.participant_id: Decimal("5.0"), b.participant_id: Decimal("30.0")},
            tee_ratings={("YELLOW", "MALE"): MEIS_AMARILLAS_M},
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=match_format,
            allowance_percentage=100,
            play_mode=PlayMode.SCRATCH,
        )

        assert all(ps.strokes_received == () for ps in result.values())
        assert all(ps.playing_handicap == 0 for ps in result.values())


class TestFreePlay:
    """Partido libre: cada uno contra el campo, con su PH entero."""

    def test_each_participant_keeps_their_own_playing_handicap(self, service):
        a = _guest("A", 18.0, TeeColor.YELLOW, Gender.MALE)
        b = _guest("B", 20.7, TeeColor.YELLOW, Gender.MALE)

        result = service.allocate(
            participants=[a, b],
            handicaps={a.participant_id: Decimal("18.0"), b.participant_id: Decimal("20.7")},
            tee_ratings={("YELLOW", "MALE"): MEIS_AMARILLAS_M},
            holes_by_stroke_index=_holes_by_stroke_index(MEIS_STROKE_INDEX),
            match_format=None,
            allowance_percentage=100,
            play_mode=PlayMode.HANDICAP,
        )

        # 23 y 27 golpes repartidos: los dos reciben, no hay diferencial
        assert len(result[a.participant_id].strokes_received) == 23
        assert len(result[b.participant_id].strokes_received) == 27

    def test_allowance_reduces_the_playing_handicap(self, service):
        a = _guest("A", 18.0, TeeColor.YELLOW, Gender.MALE)

        result = service.allocate(
            participants=[a],
            handicaps={a.participant_id: Decimal("18.0")},
            tee_ratings={("YELLOW", "MALE"): MEIS_AMARILLAS_M},
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=None,
            allowance_percentage=95,
            play_mode=PlayMode.HANDICAP,
        )

        # CH 23.40 -> x0.95 = 22.23 -> 22
        assert result[a.participant_id].playing_handicap == 22


class TestFallbacks:
    """Datos incompletos: la partida sigue siendo jugable."""

    def test_participant_without_handicap_plays_scratch(self, service):
        a = _guest("A", 18.0, TeeColor.YELLOW, Gender.MALE)
        b = _guest("B", 20.0, TeeColor.YELLOW, Gender.MALE)

        result = service.allocate(
            participants=[a, b],
            handicaps={a.participant_id: Decimal("18.0"), b.participant_id: None},
            tee_ratings={("YELLOW", "MALE"): MEIS_AMARILLAS_M},
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=MatchFormat.SINGLES,
            allowance_percentage=100,
            play_mode=PlayMode.HANDICAP,
        )

        assert result[b.participant_id].playing_handicap == 0
        # A tiene PH 23 frente a 0: recibe la diferencia entera
        assert len(result[a.participant_id].strokes_received) == 23

    def test_unknown_tee_falls_back_to_the_handicap_index(self, service):
        """Sin barra valorada se usa el propio HI, en vez de tratarlo como scratch."""
        a = _guest("A", 18.0, TeeColor.YELLOW, Gender.MALE)
        b = _guest("B", 20.7, TeeColor.YELLOW, Gender.MALE)

        result = service.allocate(
            participants=[a, b],
            handicaps={
                a.participant_id: Decimal("18.0"),
                b.participant_id: Decimal("20.7"),
            },
            tee_ratings={},  # el campo no tiene esa barra
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=MatchFormat.SINGLES,
            allowance_percentage=100,
            play_mode=PlayMode.HANDICAP,
        )

        assert result[a.participant_id].playing_handicap == 18
        assert result[b.participant_id].playing_handicap == 21
        assert len(result[b.participant_id].strokes_received) == 3

    def test_incomplete_singles_roster_gives_nobody_strokes(self, service):
        a = _guest("A", 18.0, TeeColor.YELLOW, Gender.MALE)

        result = service.allocate(
            participants=[a],
            handicaps={a.participant_id: Decimal("18.0")},
            tee_ratings={("YELLOW", "MALE"): MEIS_AMARILLAS_M},
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=MatchFormat.SINGLES,
            allowance_percentage=100,
            play_mode=PlayMode.HANDICAP,
        )

        assert result[a.participant_id].strokes_received == ()


class TestFoursomes:
    """Golpe alterno: el golpe es del equipo, no del jugador."""

    def test_both_team_members_share_the_same_allocation(self, service):
        a1 = _guest("A1", 10.0, TeeColor.YELLOW, Gender.MALE, team="A")
        a2 = _guest("A2", 12.0, TeeColor.YELLOW, Gender.MALE, team="A")
        b1 = _guest("B1", 20.0, TeeColor.YELLOW, Gender.MALE, team="B")
        b2 = _guest("B2", 24.0, TeeColor.YELLOW, Gender.MALE, team="B")

        result = service.allocate(
            participants=[a1, a2, b1, b2],
            handicaps={
                a1.participant_id: Decimal("10.0"),
                a2.participant_id: Decimal("12.0"),
                b1.participant_id: Decimal("20.0"),
                b2.participant_id: Decimal("24.0"),
            },
            tee_ratings={("YELLOW", "MALE"): MEIS_AMARILLAS_M},
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=MatchFormat.FOURSOMES,
            allowance_percentage=50,
            play_mode=PlayMode.HANDICAP,
        )

        assert (
            result[a1.participant_id].strokes_received
            == result[a2.participant_id].strokes_received
        )
        assert (
            result[b1.participant_id].strokes_received
            == result[b2.participant_id].strokes_received
        )
        # Solo recibe el equipo de mayor CH promedio
        assert result[a1.participant_id].strokes_received == ()
        assert len(result[b1.participant_id].strokes_received) > 0


class TestFourball:
    """Mejor bola: diferencias respecto al menor Course Handicap de los cuatro."""

    def test_lowest_course_handicap_plays_off_scratch(self, service):
        players = [
            _guest("A1", 5.0, TeeColor.YELLOW, Gender.MALE, team="A"),
            _guest("A2", 15.0, TeeColor.YELLOW, Gender.MALE, team="A"),
            _guest("B1", 20.0, TeeColor.YELLOW, Gender.MALE, team="B"),
            _guest("B2", 25.0, TeeColor.YELLOW, Gender.MALE, team="B"),
        ]

        result = service.allocate(
            participants=players,
            handicaps={p.participant_id: Decimal(str(hi)) for p, hi in zip(players, [5, 15, 20, 25], strict=True)},
            tee_ratings={("YELLOW", "MALE"): MEIS_AMARILLAS_M},
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=MatchFormat.FOURBALL,
            allowance_percentage=90,
            play_mode=PlayMode.HANDICAP,
        )

        assert result[players[0].participant_id].strokes_received == ()
        # Y el resto recibe en orden creciente de handicap
        counts = [len(result[p.participant_id].strokes_received) for p in players]
        assert counts == sorted(counts)


class TestParticipantStrokes:
    """El objeto que consumen la tarjeta y el calculo del resultado."""

    def test_net_score_subtracts_the_strokes_of_that_hole(self, service):
        a = _guest("A", 18.0, TeeColor.YELLOW, Gender.MALE)
        b = _guest("B", 20.7, TeeColor.YELLOW, Gender.MALE)

        result = service.allocate(
            participants=[a, b],
            handicaps={
                a.participant_id: Decimal("18.0"),
                b.participant_id: Decimal("20.7"),
            },
            tee_ratings={("YELLOW", "MALE"): MEIS_AMARILLAS_M},
            holes_by_stroke_index=_holes_by_stroke_index(MEIS_STROKE_INDEX),
            match_format=MatchFormat.SINGLES,
            allowance_percentage=100,
            play_mode=PlayMode.HANDICAP,
        )

        rival = result[b.participant_id]
        assert rival.strokes_on_hole(2) == 1  # SI 1
        assert rival.strokes_on_hole(15) == 0  # SI 18
        assert rival.net_score(2, 6) == 5
        assert rival.net_score(15, 6) == 6

    def test_net_score_never_goes_below_zero(self, service):
        a = _guest("A", 54.0, TeeColor.YELLOW, Gender.MALE)

        result = service.allocate(
            participants=[a],
            handicaps={a.participant_id: Decimal("54.0")},
            tee_ratings={("YELLOW", "MALE"): MEIS_AMARILLAS_M},
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=None,
            allowance_percentage=100,
            play_mode=PlayMode.HANDICAP,
        )

        assert result[a.participant_id].net_score(1, 1) == 0
