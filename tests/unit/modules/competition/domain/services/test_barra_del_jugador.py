"""
Desde qué barras juega cada uno (#251, PR 4): la Ryder y las partidas, igual.

Sacado de `MatchPlayersBuilder.resolve_player_data` para que las partidas de
stroke play elijan las barras con la misma regla (RyderCupAM#165): primero
(color, género) y si no, (color, sin género). Nunca la del otro género.

| Barras de la inscripción | Jugador | Valoradas en el campo        | Resultado               |
|--------------------------|---------|------------------------------|-------------------------|
| Ninguna                  | Hombre  | (Amarillas, hombre)          | Amarillas, hombre       |
| Rojas                    | Mujer   | (Rojas, mujer), (Rojas, —)   | Rojas, mujer            |
| Rojas                    | Mujer   | (Rojas, —)                   | Rojas, sin género       |
| Rojas                    | Mujer   | (Rojas, hombre)              | Rojas, sin valoración   |
| Rojas                    | Sin     | (Rojas, —)                   | Rojas, sin género       |
| Rojas                    | Sin     | (Rojas, hombre)              | Rojas, sin valoración   |
"""

from decimal import Decimal

import pytest

from src.modules.competition.domain.services.barra_del_jugador import barra_del_jugador
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.services.playing_handicap_calculator import TeeRating
from src.shared.domain.value_objects.gender import Gender

AMARILLAS_H = TeeRating(course_rating=Decimal("71.2"), slope_rating=130, par=72)
ROJAS_M = TeeRating(course_rating=Decimal("73.0"), slope_rating=128, par=72)
ROJAS = TeeRating(course_rating=Decimal("70.0"), slope_rating=120, par=72)
ROJAS_H = TeeRating(course_rating=Decimal("68.0"), slope_rating=118, par=72)


@pytest.mark.parametrize(
    ("de_la_inscripcion", "genero", "valoradas", "esperado"),
    [
        pytest.param(
            None,
            Gender.MALE,
            {("YELLOW", "MALE"): AMARILLAS_H},
            (TeeColor.YELLOW, Gender.MALE, AMARILLAS_H),
            id="sin barras elegidas, amarillas",
        ),
        pytest.param(
            TeeColor.RED,
            Gender.FEMALE,
            {("RED", "FEMALE"): ROJAS_M, ("RED", None): ROJAS},
            (TeeColor.RED, Gender.FEMALE, ROJAS_M),
            id="la de su género",
        ),
        pytest.param(
            TeeColor.RED,
            Gender.FEMALE,
            {("RED", None): ROJAS},
            (TeeColor.RED, None, ROJAS),
            id="la sin género de reserva",
        ),
        pytest.param(
            TeeColor.RED,
            Gender.FEMALE,
            {("RED", "MALE"): ROJAS_H},
            (TeeColor.RED, None, None),
            id="nunca la del otro género",
        ),
        pytest.param(
            TeeColor.RED,
            None,
            {("RED", None): ROJAS},
            (TeeColor.RED, None, ROJAS),
            id="jugador sin género, la sin género",
        ),
        pytest.param(
            TeeColor.RED,
            None,
            {("RED", "MALE"): ROJAS_H},
            (TeeColor.RED, None, None),
            id="jugador sin género, ninguna",
        ),
    ],
)
def test_barra_del_jugador(de_la_inscripcion, genero, valoradas, esperado):
    barra = barra_del_jugador(de_la_inscripcion, genero, valoradas)

    assert (barra.tee_color, barra.tee_gender, barra.tee_rating) == esperado
