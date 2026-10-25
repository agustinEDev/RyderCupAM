"""
Las partidas juntos del mismo dia salen por su hora, no por su id.

Revision de punta a punta (22 oct): dentro de un dia el orden lo decidia el
id, un uuid4 aleatorio, asi que la de la tarde podia salir detras de la de la
mañana. Ahora manda el instante real de la partida y el id solo desempata.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from src.modules.social.application.games_together import page_of
from src.modules.social.application.ports.shared_games_interface import (
    SharedGame,
    SharedGameKind,
)
from src.modules.social.domain.services.head_to_head import Relation

DIA = date(2026, 10, 18)


def _id(n: int) -> str:
    return str(UUID(int=n))


def _partida(game_id: str, hora: int | None, dia: date = DIA, minuto: int = 0) -> SharedGame:
    return SharedGame(
        kind=SharedGameKind.QUICK_MATCH,
        game_id=game_id,
        played_on=dia,
        played_at=None
        if hora is None
        else datetime.combine(dia, datetime.min.time()) + timedelta(hours=hora, minutes=minuto),
        golf_course_id=None,
        golf_course_name=None,
        format="STABLEFORD",
        relation=Relation.AGAINST,
        outcome=None,
    )


def _todas(partidas: list[SharedGame], limit: int) -> tuple[list[str], int]:
    vistas, cursor, paginas = [], None, 0
    # Con tope: un cursor que no avanza no puede colgar la suite
    while paginas < len(partidas) + 1:
        pagina = page_of(partidas, cursor, limit=limit)
        paginas += 1
        vistas.extend(g.id for g in pagina.games)
        cursor = pagina.next_cursor
        if cursor is None:
            break
    return vistas, paginas


def test_el_mismo_dia_sale_de_la_mas_tardia_a_la_mas_temprana():
    """
    Given tres partidas del mismo dia cuyo id va al reves que su hora /
    When pido la pagina / Then salen por la hora: tarde, mediodia, mañana.
    """
    temprano = _partida(_id(3), hora=9)
    mediodia = _partida(_id(2), hora=13)
    tarde = _partida(_id(1), hora=18)

    pagina = page_of([temprano, tarde, mediodia], None)

    assert [g.id for g in pagina.games] == [tarde.game_id, mediodia.game_id, temprano.game_id]


def test_el_dia_sigue_mandando_sobre_la_hora():
    """Una partida de ayer a ultima hora va detras de una de hoy a primera."""
    hoy_temprano = _partida(_id(1), hora=7)
    ayer_tarde = _partida(_id(2), hora=21, dia=DIA - timedelta(days=1))

    pagina = page_of([ayer_tarde, hoy_temprano], None)

    assert [g.id for g in pagina.games] == [hoy_temprano.game_id, ayer_tarde.game_id]


def test_a_la_misma_hora_desempata_el_id():
    """Dos a la misma hora salen siempre en el mismo orden: el del id, de mayor a menor."""
    a = _partida(_id(1), hora=10)
    b = _partida(_id(2), hora=10)

    assert [g.id for g in page_of([a, b], None).games] == [b.game_id, a.game_id]
    assert [g.id for g in page_of([b, a], None).games] == [b.game_id, a.game_id]


def test_paginar_varias_del_mismo_dia_sin_repetir_ni_saltar():
    """
    Given siete partidas del mismo dia —dos a la misma hora y una sin hora— y
    alguna de otro dia / When paso paginas de 2 / Then salen todas una vez, en
    orden: por dia, por hora y por id.
    """
    partidas = [
        _partida(_id(50), hora=8),
        _partida(_id(10), hora=17, minuto=30),
        _partida(_id(40), hora=12),
        _partida(_id(20), hora=12),
        _partida(_id(30), hora=15),
        _partida(_id(60), hora=None),
        _partida(_id(70), hora=19),
        _partida(_id(5), hora=9, dia=DIA - timedelta(days=1)),
        _partida(_id(99), hora=9, dia=DIA + timedelta(days=1)),
    ]

    vistas, paginas = _todas(partidas, limit=2)

    assert vistas == [
        _id(99),  # el dia siguiente
        _id(70),  # 19:00
        _id(10),  # 17:30
        _id(30),  # 15:00
        _id(40),  # 12:00, id mayor
        _id(20),  # 12:00, id menor
        _id(50),  # 08:00
        _id(60),  # sin hora: al principio del dia
        _id(5),  # ayer
    ]
    assert paginas == 5


@pytest.mark.parametrize(
    "cursor",
    [
        f"{DIA.isoformat()}|0001-01-01T00:00:00+01:00|{_id(1)}",
        f"{DIA.isoformat()}|9999-12-31T23:59:59-01:00|{_id(1)}",
        f"{DIA.isoformat()}|no-es-una-hora|{_id(1)}",
        f"no-es-un-dia|2026-10-18T10:00:00|{_id(1)}",
        f"{DIA.isoformat()}|2026-10-18T10:00:00|no-es-un-id",
        f"{DIA.isoformat()}|{_id(1)}",
    ],
)
def test_un_cursor_corrupto_o_extremo_da_la_primera_pagina(cursor):
    partidas = [_partida(_id(n), hora=8 + n) for n in range(1, 4)]

    pagina = page_of(partidas, cursor)

    assert [g.id for g in pagina.games] == [_id(3), _id(2), _id(1)]


def test_h5_una_rapida_dice_su_instante_en_utc_y_un_torneo_no():
    """
    H5 (25 oct 2026): `played_on` es el día en UTC; con `played_at` y su zona el
    cliente pone la partida en su día local. El torneo no lo lleva: su día es el
    de la ronda, y un instante a medianoche saldría el día anterior en América.
    """
    rapida = _partida(_id(1), 22)
    torneo = SharedGame(
        kind=SharedGameKind.TOURNAMENT_MATCH,
        game_id=_id(2),
        played_on=DIA,
        played_at=datetime.combine(DIA, datetime.min.time()),
        golf_course_id=None,
        golf_course_name=None,
        format="SINGLES",
        relation=Relation.AGAINST,
        outcome=None,
    )

    por_id = {g.id: g for g in page_of([rapida, torneo], None, limit=10).games}

    assert por_id[_id(1)].played_at == datetime(2026, 10, 18, 22, 0, tzinfo=UTC)
    assert por_id[_id(2)].played_at is None
