"""
El cableado de los avisos de horario (G): cada caso de uso que mueve salidas
recibe el publicador de Actividad, y los que no avisan no lo reciben.

Sin esto, un proveedor que se olvide el publicador deja el aviso mudo sin que
ningun test de caso de uso lo note: ellos montan el suyo a mano.
"""

from unittest.mock import MagicMock

import pytest

from src.config import dependencies as d
from src.modules.competition.application.use_cases.partidas_use_case import VerPartidasUseCase

PUBLICADOR = object()


def _uows():
    uow = MagicMock()
    gc_uow = MagicMock()
    user_uow = MagicMock()
    return {"uow": uow, "gc_uow": gc_uow, "user_uow": user_uow}


def _publicador_de(caso_de_uso):
    return caso_de_uso._actividad._publisher


@pytest.mark.parametrize(
    ("proveedor", "extra"),
    [
        (d.get_generar_partidas_use_case, {"jugadores": MagicMock()}),
        (d.get_mover_jugador_de_partida_use_case, {"jugadores": MagicMock()}),
        (d.get_reordenar_partidas_use_case, {}),
        (d.get_borrar_partidas_use_case, {}),
    ],
)
def test_stroke_play_groups_get_the_publisher(proveedor, extra):
    caso = proveedor(**_uows(), **extra, actividad=PUBLICADOR)

    assert _publicador_de(caso) is PUBLICADOR


def test_viewing_the_groups_does_not_need_it():
    caso = d.get_ver_partidas_use_case(**_uows())

    assert isinstance(caso, VerPartidasUseCase)


def test_update_round_reopen_and_take_a_place():
    uows = _uows()
    ronda = d.get_update_round_use_case(
        uow=uows["uow"],
        gc_uow=uows["gc_uow"],
        jugadores=MagicMock(),
        reloj=lambda: None,
        actividad=PUBLICADOR,
    )
    reabrir = d.get_reopen_enrollments_use_case(
        uow=uows["uow"], gc_uow=uows["gc_uow"], actividad=PUBLICADOR
    )
    plaza = d.get_coger_plaza_use_case(uow=uows["uow"], gc_uow=uows["gc_uow"], actividad=PUBLICADOR)

    assert _publicador_de(ronda) is PUBLICADOR
    assert _publicador_de(reabrir) is PUBLICADOR
    assert _publicador_de(plaza) is PUBLICADOR


def test_ryder_matches_by_hand_reassigning_and_resetting():
    uows = _uows()
    generar = d.get_generate_matches_use_case(
        **uows,
        scoring_service=MagicMock(),
        handicap_service=MagicMock(),
        actividad=PUBLICADOR,
    )
    reasignar = d.get_reassign_match_players_use_case(
        **uows, scoring_service=MagicMock(), actividad=PUBLICADOR
    )
    rehacer = d.get_reset_envelopes_use_case(
        uow=uows["uow"], user_uow=uows["user_uow"], actividad=PUBLICADOR
    )

    assert _publicador_de(generar) is PUBLICADOR
    assert _publicador_de(reasignar) is PUBLICADOR
    assert _publicador_de(rehacer) is PUBLICADOR


@pytest.mark.parametrize(
    "proveedor",
    [
        d.get_submit_envelope_use_case,
        d.get_envelopes_use_case,
        d.get_reveal_envelopes_use_case,
    ],
)
def test_opening_the_envelopes_generates_with_the_publisher(proveedor):
    caso = proveedor(**_uows(), scoring_service=MagicMock(), actividad=PUBLICADOR)

    assert _publicador_de(caso._desk._generador) is PUBLICADOR


def test_the_schedule_opens_them_with_the_publisher_too():
    caso = d.get_get_schedule_use_case(**_uows(), scoring_service=MagicMock(), actividad=PUBLICADOR)

    assert _publicador_de(caso._sobres._generador) is PUBLICADOR


def test_no_show_and_withdrawal_tell_who_is_moved():
    """G3, 22 oct: quien se recoloca por un no presentado o una baja recibe su aviso."""
    uows = _uows()
    no_presentado = d.get_marcar_no_presentado_use_case(
        uow=uows["uow"], gc_uow=uows["gc_uow"], reloj=lambda: None, actividad=PUBLICADOR
    )
    baja = d.get_withdraw_enrollment_use_case(
        uow=uows["uow"], gc_uow=uows["gc_uow"], actividad=PUBLICADOR
    )

    assert _publicador_de(no_presentado) is PUBLICADOR
    assert _publicador_de(baja) is PUBLICADOR
