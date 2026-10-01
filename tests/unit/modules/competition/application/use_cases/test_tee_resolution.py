"""
Qué barra juega cada jugador al generar o reasignar partidos (RyderCupAM#165).

Primero la de su color y su género; si el campo no la tiene, la de su color sin
género. Y el jugador guarda el género de la barra con la que juega de verdad:
si cae a la sin género, se guarda sin género, porque es esa barra la que se usa
después para su tarjeta y su reparto.

Hasta el 2 oct 2026 nada lo comprobaba: las mutaciones que guardaban el género
del jugador aunque jugara la barra sin género pasaban todos los tests.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.use_cases.generate_matches_use_case import (
    GenerateMatchesUseCase,
)
from src.modules.competition.application.use_cases.reassign_match_players_use_case import (
    ReassignMatchPlayersUseCase,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.playing_handicap_calculator import TeeRating
from src.shared.domain.value_objects.gender import Gender

AMARILLAS_HOMBRE = TeeRating(Decimal("72.0"), 130, 72)
AMARILLAS_SIN_GENERO = TeeRating(Decimal("70.0"), 120, 72)
HOYOS = list(range(1, 19))


def _inscripcion():
    return SimpleNamespace(tee_color=TeeColor.YELLOW, custom_handicap=None)


def _generate() -> GenerateMatchesUseCase:
    return GenerateMatchesUseCase(MagicMock(), MagicMock(), MagicMock())


def _reassign() -> ReassignMatchPlayersUseCase:
    return ReassignMatchPlayersUseCase(MagicMock(), MagicMock(), MagicMock())


def _resuelto_por_generate(tee_ratings, genero):
    user_id = UserId(str(uuid4()))
    _, tee_gender, tee_rating, _ = _generate()._resolve_player_data(
        user_id,
        {str(user_id.value): _inscripcion()},
        tee_ratings,
        {},
        {str(user_id.value): genero} if genero else {},
    )
    return tee_gender, tee_rating


def _resuelto_por_reassign(tee_ratings, genero):
    uid = str(uuid4())
    jugador = _reassign()._build_match_player(
        uid,
        {uid: _inscripcion()},
        tee_ratings,
        allowance=100,
        is_scratch=False,
        user_handicap_map={},
        holes_by_stroke_index=HOYOS,
        user_gender_map={uid: genero} if genero else {},
    )
    return jugador.tee_gender


class TestGenerateMatches:
    def test_con_su_barra_juega_con_su_genero(self):
        tee_ratings = {("YELLOW", "MALE"): AMARILLAS_HOMBRE, ("YELLOW", None): AMARILLAS_SIN_GENERO}

        assert _resuelto_por_generate(tee_ratings, Gender.MALE) == (Gender.MALE, AMARILLAS_HOMBRE)

    def test_sin_su_barra_juega_la_sin_genero_y_la_guarda_sin_genero(self):
        tee_ratings = {("YELLOW", None): AMARILLAS_SIN_GENERO}

        assert _resuelto_por_generate(tee_ratings, Gender.MALE) == (None, AMARILLAS_SIN_GENERO)

    def test_sin_genero_conocido_juega_la_sin_genero(self):
        tee_ratings = {("YELLOW", "MALE"): AMARILLAS_HOMBRE, ("YELLOW", None): AMARILLAS_SIN_GENERO}

        assert _resuelto_por_generate(tee_ratings, None) == (None, AMARILLAS_SIN_GENERO)


class TestReassignMatchPlayers:
    def test_con_su_barra_juega_con_su_genero(self):
        tee_ratings = {("YELLOW", "MALE"): AMARILLAS_HOMBRE, ("YELLOW", None): AMARILLAS_SIN_GENERO}

        assert _resuelto_por_reassign(tee_ratings, Gender.MALE) == Gender.MALE

    def test_sin_su_barra_juega_la_sin_genero_y_la_guarda_sin_genero(self):
        assert _resuelto_por_reassign({("YELLOW", None): AMARILLAS_SIN_GENERO}, Gender.MALE) is None

    def test_sin_ninguna_de_las_dos_no_se_puede_generar(self):
        """Lo de hoy: un 400 con un mensaje que dice la barra que falta."""
        with pytest.raises(ValueError, match="tee rating"):
            _resuelto_por_reassign({("RED", None): AMARILLAS_SIN_GENERO}, Gender.MALE)
