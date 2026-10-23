"""
Una partida rapida que no cuenta sale en «Partidas juntos» como sin terminar
(tabla del 22 oct 2026, A) y no suma en el cara a cara.
"""

from datetime import date
from uuid import UUID

from src.modules.social.application.games_together import head_to_head_of, page_of
from src.modules.social.application.ports.shared_games_interface import (
    SharedGame,
    SharedGameKind,
)
from src.modules.social.domain.services.head_to_head import Outcome, Relation


def _partida(n: int, outcome: Outcome | None, unfinished: bool = False) -> SharedGame:
    return SharedGame(
        kind=SharedGameKind.QUICK_MATCH,
        game_id=str(UUID(int=n)),
        played_on=date(2026, 10, n),
        golf_course_id=None,
        golf_course_name=None,
        format="SINGLES",
        relation=Relation.AGAINST,
        outcome=outcome,
        unfinished=unfinished,
    )


def test_la_sin_terminar_sale_con_resultado_unfinished():
    pagina = page_of([_partida(1, None, unfinished=True), _partida(2, Outcome.WON)], None)

    assert [g.result for g in pagina.games] == ["WON", "UNFINISHED"]


def test_sin_resultado_por_otra_razon_sigue_en_none():
    """Sin hándicap o sin campo: no se juzga, pero no está a medias."""
    pagina = page_of([_partida(1, None)], None)

    assert pagina.games[0].result is None


def test_la_sin_terminar_no_suma_en_el_cara_a_cara():
    cara_a_cara = head_to_head_of([_partida(1, None, unfinished=True), _partida(2, Outcome.LOST)])

    assert cara_a_cara is not None
    assert cara_a_cara.against is not None
    assert (cara_a_cara.against.won, cara_a_cara.against.halved, cara_a_cara.against.lost) == (
        0,
        0,
        1,
    )


def test_solo_sin_terminar_no_hay_cara_a_cara():
    assert head_to_head_of([_partida(1, None, unfinished=True)]) is None
