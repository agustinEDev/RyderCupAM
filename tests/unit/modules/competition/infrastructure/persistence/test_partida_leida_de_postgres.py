"""
Una partida leída de sus filas (QA del 11 oct 2026).

| Caso                                                    | Resultado                      |
|---------------------------------------------------------|--------------------------------|
| Guardada antes del 11 oct: un retirado sigue marcando   | Se rehace el círculo al leerla |
| Guardada después                                        | Tal cual                       |
| Un jugador traído de otra partida                       | En `traidos`                   |
"""

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.infrastructure.persistence.sqlalchemy.partida_repository import (
    SQLAlchemyPartidaRepository,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId

A, B, C = UserId.generate(), UserId.generate(), UserId.generate()


def _fila(user_id, marca, tarjeta="JUGANDO", traido=False):
    return SimpleNamespace(
        user_id=user_id,
        handicap_index=Decimal("10.0"),
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        tee_gender=None,
        strokes_by_hole=[0] * 18,
        pars_by_hole=[4] * 18,
        card_status=tarjeta,
        marks_user_id=marca,
        brought_in=traido,
    )


GRUPO = SimpleNamespace(
    id=str(uuid.uuid4()),
    competition_id=CompetitionId(uuid.uuid4()),
    round_id=RoundId.generate(),
    number=1,
    status="IN_PROGRESS",
    created_at=date(2030, 10, 11),
)


def test_a_withdrawn_player_still_marking_is_rebuilt():
    partida = SQLAlchemyPartidaRepository._partida(
        GRUPO, [_fila(A, B), _fila(B, C), _fila(C, A, tarjeta="RETIRADO")]
    )

    assert partida.marcadores == {A: B, B: A}


def test_a_circle_saved_after_is_read_as_it_is():
    partida = SQLAlchemyPartidaRepository._partida(
        GRUPO, [_fila(A, B), _fila(B, A), _fila(C, None, tarjeta="RETIRADO")]
    )

    assert partida.marcadores == {A: B, B: A}


def test_who_was_brought_in():
    partida = SQLAlchemyPartidaRepository._partida(GRUPO, [_fila(A, B), _fila(B, A, traido=True)])

    assert partida.traidos == {B}
