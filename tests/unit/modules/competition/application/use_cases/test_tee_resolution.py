"""
Qué barra juega cada jugador al generar o reasignar partidos (RyderCupAM#165).

Primero la de su color y su género; si el campo no la tiene, la de su color sin
género. Y el jugador guarda el género de la barra con la que juega de verdad:
si cae a la sin género, se guarda sin género, porque es esa barra la que se usa
después para su tarjeta y su reparto.

Hasta el 2 oct 2026 nada lo comprobaba: las mutaciones que guardaban el género
del jugador aunque jugara la barra sin género pasaban todos los tests. Desde el
3 oct (BE #477) generar y reasignar resuelven con la misma pieza,
`MatchPlayersBuilder`, y estos casos la prueban a ella.
"""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.application.services.match_players_builder import (
    MatchPlayersBuilder,
    TeeColorNotFoundError,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
    TeeRating,
)
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat

AMARILLAS_HOMBRE = TeeRating(Decimal("72.0"), 130, 72)
AMARILLAS_SIN_GENERO = TeeRating(Decimal("70.0"), 120, 72)
HOYOS = list(range(1, 19))


def _inscripcion():
    return SimpleNamespace(tee_color=TeeColor.YELLOW, custom_handicap=None)


def _resuelto(tee_ratings, genero):
    user_id = UserId(str(uuid4()))
    _, tee_gender, tee_rating, _ = MatchPlayersBuilder().resolve_player_data(
        user_id,
        {str(user_id.value): _inscripcion()},
        tee_ratings,
        {},
        {str(user_id.value): genero} if genero else {},
    )
    return tee_gender, tee_rating


def _jugador_construido(tee_ratings, genero):
    """El género que se GUARDA en el jugador, a través del reparto completo."""
    a, b = UserId(str(uuid4())), UserId(str(uuid4()))
    (jugador,), _ = MatchPlayersBuilder().build(
        MatchFormat.SINGLES,
        [a],
        [b],
        {str(a.value): _inscripcion(), str(b.value): _inscripcion()},
        tee_ratings,
        PlayingHandicapCalculator(),
        100,
        False,
        {},
        HOYOS,
        {str(a.value): genero, str(b.value): genero} if genero else {},
    )
    return jugador.tee_gender


class TestResolvePlayerData:
    def test_con_su_barra_juega_con_su_genero(self):
        tee_ratings = {("YELLOW", "MALE"): AMARILLAS_HOMBRE, ("YELLOW", None): AMARILLAS_SIN_GENERO}

        assert _resuelto(tee_ratings, Gender.MALE) == (Gender.MALE, AMARILLAS_HOMBRE)

    def test_sin_su_barra_juega_la_sin_genero_y_la_guarda_sin_genero(self):
        tee_ratings = {("YELLOW", None): AMARILLAS_SIN_GENERO}

        assert _resuelto(tee_ratings, Gender.MALE) == (None, AMARILLAS_SIN_GENERO)

    def test_sin_genero_conocido_juega_la_sin_genero(self):
        tee_ratings = {("YELLOW", "MALE"): AMARILLAS_HOMBRE, ("YELLOW", None): AMARILLAS_SIN_GENERO}

        assert _resuelto(tee_ratings, None) == (None, AMARILLAS_SIN_GENERO)


class TestElJugadorGuardaLaBarraConLaQueJuega:
    def test_con_su_barra_guarda_su_genero(self):
        tee_ratings = {("YELLOW", "MALE"): AMARILLAS_HOMBRE, ("YELLOW", None): AMARILLAS_SIN_GENERO}

        assert _jugador_construido(tee_ratings, Gender.MALE) == Gender.MALE

    def test_con_la_sin_genero_la_guarda_sin_genero(self):
        assert _jugador_construido({("YELLOW", None): AMARILLAS_SIN_GENERO}, Gender.MALE) is None

    def test_sin_ninguna_de_las_dos_no_se_puede_generar(self):
        """Un 400 con un mensaje que dice la barra que falta."""
        with pytest.raises(TeeColorNotFoundError, match="tee rating"):
            _jugador_construido({("RED", None): AMARILLAS_SIN_GENERO}, Gender.MALE)


class TestPlusEnIndividual:
    """El plus cuenta como negativo también en competición (BE #165)."""

    NEUTRA = TeeRating(Decimal("72.0"), 113, 72)

    def test_el_rival_recibe_la_diferencia_completa(self):
        plus, diez = UserId(str(uuid4())), UserId(str(uuid4()))
        inscripciones = {
            str(plus.value): SimpleNamespace(
                tee_color=TeeColor.YELLOW, custom_handicap=Decimal("-2.0")
            ),
            str(diez.value): SimpleNamespace(
                tee_color=TeeColor.YELLOW, custom_handicap=Decimal("10.0")
            ),
        }

        (jugador_plus,), (jugador_diez,) = MatchPlayersBuilder().build(
            MatchFormat.SINGLES,
            [plus],
            [diez],
            inscripciones,
            {("YELLOW", None): self.NEUTRA},
            PlayingHandicapCalculator(),
            100,
            False,
            {},
            HOYOS,
            {},
        )

        assert jugador_plus.playing_handicap == -2
        assert list(jugador_plus.strokes_received) == []
        assert len(jugador_diez.strokes_received) == 12
