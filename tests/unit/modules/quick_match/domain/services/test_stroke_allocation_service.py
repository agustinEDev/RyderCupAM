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
        assert result[me.participant_id].strokes_by_hole == {}
        # 27 - 23 = 4 golpes, en los hoyos de SI 1, 2, 3 y 4 -> hoyos 2, 11, 7 y 17
        assert sorted(result[rival.participant_id].strokes_by_hole) == [2, 7, 11, 17]

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
        assert result[rival.participant_id].strokes_by_hole == {}
        assert result[me.participant_id].total_strokes == 4


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

        assert all(ps.strokes_by_hole == {} for ps in result.values())
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
        assert result[a.participant_id].total_strokes == 23
        assert result[b.participant_id].total_strokes == 27

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
        assert result[a.participant_id].total_strokes == 23

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
        assert result[b.participant_id].total_strokes == 3

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

        assert result[a.participant_id].strokes_by_hole == {}


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
            result[a1.participant_id].strokes_by_hole
            == result[a2.participant_id].strokes_by_hole
        )
        assert (
            result[b1.participant_id].strokes_by_hole
            == result[b2.participant_id].strokes_by_hole
        )
        # Solo recibe el equipo de mayor CH promedio
        assert result[a1.participant_id].strokes_by_hole == {}
        assert result[b1.participant_id].total_strokes > 0


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

        assert result[players[0].participant_id].strokes_by_hole == {}
        # Y el resto recibe en orden creciente de handicap
        counts = [result[p.participant_id].total_strokes for p in players]
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


class TestPlusHandicap:
    """
    Handicap plus: el jugador CEDE golpes al campo (Regla WHS 8.2).

    No habia ni un test de esto, y por eso paso desapercibido que el reparto
    acotaba el Playing Handicap a cero: la tarjeta daba cero golpes y la
    clasificacion seguia descontandolos, dos totales distintos en la misma
    pantalla para el mismo jugador.
    """

    def test_plus_handicap_gives_strokes_back_in_free_play(self, service):
        """
        Given un jugador de handicap plus en partido libre
        When se reparte el handicap
        Then su Playing Handicap es negativo y cede golpes, no recibe
        """
        a = _guest("Plus", -2.0, TeeColor.YELLOW, Gender.MALE)

        result = service.allocate(
            participants=[a],
            handicaps={a.participant_id: Decimal("-2.0")},
            # Campo neutro (slope 113, CR = par) para que el PH sea el HI exacto
            tee_ratings={
                ("YELLOW", "MALE"): TeeRating(
                    course_rating=Decimal("72.0"), slope_rating=113, par=72
                )
            },
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=None,
            allowance_percentage=100,
            play_mode=PlayMode.HANDICAP,
        )

        strokes = result[a.participant_id]
        assert strokes.playing_handicap == -2
        assert strokes.total_strokes == -2
        # Se ceden desde el hoyo mas facil hacia atras: SI 18 y 17
        assert strokes.strokes_by_hole == {18: -1, 17: -1}

    def test_giving_back_a_stroke_raises_the_net_score(self, service):
        a = _guest("Plus", -2.0, TeeColor.YELLOW, Gender.MALE)

        result = service.allocate(
            participants=[a],
            handicaps={a.participant_id: Decimal("-2.0")},
            tee_ratings={
                ("YELLOW", "MALE"): TeeRating(
                    course_rating=Decimal("72.0"), slope_rating=113, par=72
                )
            },
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=None,
            allowance_percentage=100,
            play_mode=PlayMode.HANDICAP,
        )

        strokes = result[a.participant_id]
        assert strokes.net_score(18, 4) == 5  # cede golpe: su neto empeora
        assert strokes.net_score(1, 4) == 4  # aqui no cede nada

    def test_match_play_still_clamps_each_playing_handicap_at_zero(self, service):
        """
        Given un plus contra un handicap alto en match play
        When se reparte
        Then el plus juega off scratch y el rival recibe la diferencia completa

        En match play la ventaja la recoge la diferencia entre los dos Playing
        Handicaps, y el WHS acota cada uno a cero antes de restarlos: nadie cede
        golpes al campo, se los da al rival.
        """
        plus = _guest("Plus", -2.0, TeeColor.YELLOW, Gender.MALE)
        high = _guest("High", 20.0, TeeColor.YELLOW, Gender.MALE)
        neutral = TeeRating(course_rating=Decimal("72.0"), slope_rating=113, par=72)

        result = service.allocate(
            participants=[plus, high],
            handicaps={
                plus.participant_id: Decimal("-2.0"),
                high.participant_id: Decimal("20.0"),
            },
            tee_ratings={("YELLOW", "MALE"): neutral},
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=MatchFormat.SINGLES,
            allowance_percentage=100,
            play_mode=PlayMode.HANDICAP,
        )

        assert result[plus.participant_id].playing_handicap == 0
        assert result[high.participant_id].playing_handicap == 20
        assert result[plus.participant_id].strokes_by_hole == {}
        assert result[high.participant_id].total_strokes == 20


class TestAllocateByHole:
    """El reparto con signo, aislado."""

    def test_wraps_around_past_eighteen(self, service):
        allocation = service.allocate_by_hole(23, _holes_by_stroke_index())

        assert allocation[1] == 2  # SI 1
        assert allocation[5] == 2  # SI 5
        assert allocation[6] == 1  # SI 6
        assert allocation[18] == 1  # SI 18
        assert sum(allocation.values()) == 23

    def test_zero_allocates_nothing(self, service):
        assert service.allocate_by_hole(0, _holes_by_stroke_index()) == {}

    def test_no_holes_allocates_nothing(self, service):
        assert service.allocate_by_hole(10, []) == {}


class TestReviewFindings:
    """
    Casos que el code review destapó y que no tenían ni un test.

    Todos comparten el mismo patrón: el reparto salía silenciosamente distinto
    del que espera el WHS o del que calcula el frontend, sin que nada fallase.
    """

    def test_falls_back_to_a_genderless_tee(self, service):
        """
        Given un campo dado de alta a mano, con la salida sin genero
        When un participante la elige (el DTO le obliga a mandar color y genero)
        Then se encuentra igual, en vez de caer al Handicap Index

        Sin la reserva a (color, None) la busqueda no acertaba nunca: un 18.0
        salia con 18 golpes en vez de 23. Cinco de diferencia, en silencio.
        """
        a = _guest("A", 18.0, TeeColor.YELLOW, Gender.MALE)

        result = service.allocate(
            participants=[a],
            handicaps={a.participant_id: Decimal("18.0")},
            tee_ratings={("YELLOW", None): MEIS_AMARILLAS_M},
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=None,
            allowance_percentage=100,
            play_mode=PlayMode.HANDICAP,
        )

        assert result[a.participant_id].playing_handicap == 23

    def test_allocates_on_the_holes_of_the_tee_being_played(self, service):
        """
        Given dos barras del mismo campo con stroke index distintos
        When cada jugador juega la suya
        Then cada uno recibe en los hoyos de SU barra

        Pasa en 56 de los 800 campos federados importados. `golf_course.reference_card`
        es solo la tarjeta de la primera barra, asi que sin esto el que juega la
        otra recibia los golpes en los hoyos equivocados.
        """
        her = _guest("Ella", 20.0, TeeColor.YELLOW, Gender.FEMALE)

        # Su barra tiene el orden invertido respecto al del campo
        reversed_order = list(range(18, 0, -1))

        result = service.allocate(
            participants=[her],
            handicaps={her.participant_id: Decimal("20.0")},
            tee_ratings={("YELLOW", "FEMALE"): MEIS_AMARILLAS_M},
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=None,
            allowance_percentage=100,
            play_mode=PlayMode.HANDICAP,
            holes_by_stroke_index_by_tee={("YELLOW", "FEMALE"): reversed_order},
        )

        strokes = result[her.participant_id]
        # PH 25: dos golpes en los 7 mas dificiles de SU barra, que son el 18..12
        assert strokes.strokes_on_hole(18) == 2
        assert strokes.strokes_on_hole(1) == 1

    def test_allowance_also_applies_without_a_usable_tee(self, service):
        """
        Given un participante sin barra valorable en un partido libre al 95%
        When se calcula su reparto
        Then el allowance se le aplica igual

        Antes jugaba al 100% de su handicap mientras el resto de la partida
        jugaba al 95%: salia ganando por no tener datos.
        """
        a = _guest("A", 20.0, TeeColor.YELLOW, Gender.MALE)

        result = service.allocate(
            participants=[a],
            handicaps={a.participant_id: Decimal("20.0")},
            tee_ratings={},
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=None,
            allowance_percentage=95,
            play_mode=PlayMode.HANDICAP,
        )

        # 20 x 0.95 = 19, no 20
        assert result[a.participant_id].playing_handicap == 19

    def test_rounds_half_away_from_zero_like_the_rest_of_the_calculation(self, service):
        """
        Given un Handicap Index acabado en .5 y sin barra valorable
        When se redondea
        Then se aleja del cero, como `PlayingHandicapCalculator` y el frontend

        `Decimal.to_integral_value()` redondea al par por defecto: 20.5 -> 20.
        El resto del calculo usa ROUND_HALF_UP, asi que partia el empate para el
        lado contrario justo en los handicaps acabados en .5.
        """
        a = _guest("A", 20.5, TeeColor.YELLOW, Gender.MALE)

        result = service.allocate(
            participants=[a],
            handicaps={a.participant_id: Decimal("20.5")},
            tee_ratings={},
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=None,
            allowance_percentage=100,
            play_mode=PlayMode.HANDICAP,
        )

        assert result[a.participant_id].playing_handicap == 21

    def test_fourball_shows_the_playing_handicap_not_the_difference(self, service):
        """
        Given un fourball
        When se reparte
        Then cada uno conserva SU handicap de juego, aunque reciba la diferencia

        Guardar el diferencial ahi hacia que la tarjeta dijese "Hcp de juego 14
        - recibe 14 golpes": el mismo numero dos veces, y ninguno era su
        handicap de juego.
        """
        players = [
            _guest("A1", 5.0, TeeColor.YELLOW, Gender.MALE, team="A"),
            _guest("A2", 15.0, TeeColor.YELLOW, Gender.MALE, team="A"),
            _guest("B1", 20.0, TeeColor.YELLOW, Gender.MALE, team="B"),
            _guest("B2", 25.0, TeeColor.YELLOW, Gender.MALE, team="B"),
        ]

        result = service.allocate(
            participants=players,
            handicaps={
                p.participant_id: Decimal(str(hi))
                for p, hi in zip(players, [5, 15, 20, 25], strict=True)
            },
            tee_ratings={("YELLOW", "MALE"): MEIS_AMARILLAS_M},
            holes_by_stroke_index=_holes_by_stroke_index(),
            match_format=MatchFormat.FOURBALL,
            allowance_percentage=90,
            play_mode=PlayMode.HANDICAP,
        )

        best = result[players[0].participant_id]
        worst = result[players[3].participant_id]
        # El mejor juega off scratch pero conserva su handicap de juego
        assert best.total_strokes == 0
        assert best.playing_handicap > 0
        # Y el peor recibe menos golpes de los que dice su handicap de juego
        assert worst.playing_handicap > worst.total_strokes

    def test_an_unknown_match_format_fails_loudly(self, service):
        """Un formato nuevo sin reparto propio no debe caer en el de golpe alterno."""

        class FakeFormat:
            value = "SCRAMBLE"

        with pytest.raises(ValueError, match="No stroke allocation defined"):
            service.allocate(
                participants=[],
                handicaps={},
                tee_ratings={},
                holes_by_stroke_index=_holes_by_stroke_index(),
                match_format=FakeFormat(),
                allowance_percentage=100,
                play_mode=PlayMode.HANDICAP,
            )
