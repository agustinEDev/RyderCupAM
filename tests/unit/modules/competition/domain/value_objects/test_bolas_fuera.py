"""
Las bolas que no cuentan en un fourball con retirados (25 oct 2026).

| #  | fila                                                          | cuenta |
|----|---------------------------------------------------------------|--------|
| B1 | de alguien que juega                                          | sí     |
| B2 | del retirado, validada (la marcó y confirmó antes de irse)    | sí     |
| B3 | del retirado, sin validar                                     | no     |
| B4 | de un hoyo que se cerró sin su bola mientras estuvo fuera     | no     |
| B5 | de otro hoyo del que volvió                                   | sí     |
| B6 | sin nadie fuera                                               | todas  |
"""

from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.value_objects.bolas_fuera import BolasFuera
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.user.domain.value_objects.user_id import UserId

A1 = UserId.generate()
A2 = UserId.generate()
PARTIDO = MatchId.generate()


def _fila(jugador: UserId, hoyo: int = 1, validada: bool = True) -> HoleScore:
    fila = HoleScore.create(
        match_id=PARTIDO, hole_number=hoyo, player_user_id=jugador, team="A", strokes_received=0
    )
    if validada:
        fila.set_own_score(4)
        fila.set_marker_score(4)
    fila.recalculate_validation()
    return fila


def test_b1_someone_playing_counts():
    """Given A1 retirado / When la fila es de A2 / Then cuenta."""
    assert BolasFuera(retirados=frozenset({A1})).cuenta(_fila(A2, validada=False))


def test_b2_his_validated_ball_counts():
    """Given A1 retirado / When su fila está validada / Then cuenta."""
    assert BolasFuera(retirados=frozenset({A1})).cuenta(_fila(A1))


def test_b3_his_unvalidated_ball_does_not():
    """Given A1 retirado / When su fila no está validada / Then no cuenta."""
    assert not BolasFuera(retirados=frozenset({A1})).cuenta(_fila(A1, validada=False))


def test_b4_a_hole_closed_without_him_stays_without_his_ball():
    """Given A1 volvió y el 3 se cerró sin él / When su fila del 3, aunque esté validada / Then no cuenta."""
    fuera = BolasFuera(hoyos_sin_su_bola={A1: frozenset({3})})
    assert not fuera.cuenta(_fila(A1, hoyo=3))
    assert not fuera.cuenta(_fila(A1, hoyo=3, validada=False))


def test_b5_other_holes_count_again():
    """Given A1 volvió y solo el 3 se cerró sin él / When su fila del 4 / Then cuenta."""
    fuera = BolasFuera(hoyos_sin_su_bola={A1: frozenset({3})})
    assert fuera.cuenta(_fila(A1, hoyo=4, validada=False))


def test_b6_nobody_out_everything_counts_and_it_is_falsy():
    """Given nadie fuera / When cualquier fila / Then cuenta, y el objeto es falso."""
    fuera = BolasFuera()
    assert fuera.cuenta(_fila(A1, validada=False))
    assert not fuera
    assert BolasFuera(retirados=frozenset({A1}))
