"""
Reabrir la tarjeta de un no presentado cuando ya juegan 4 (12 oct 2026).

| Caso                              | Respuesta              |
|-----------------------------------|------------------------|
| PartidaLlenaError al reabrir      | 409 GROUP_FULL         |
| Mover a un no presentado          | 400 con su frase       |
"""

import json

from src.modules.competition.domain.entities.partida import PartidaLlenaError
from src.modules.competition.infrastructure.api.v1.tee_group_scoring_routes import _respuesta


def test_a_full_group_is_a_conflict():
    respuesta = _respuesta(PartidaLlenaError("llena"))

    assert respuesta.status_code == 409
    cuerpo = json.loads(respuesta.body)
    assert cuerpo["error_code"] == "GROUP_FULL"
    # Sin número: en una franja de 3 no son 4 (CodeRabbit en la #543)
    assert not any(c.isdigit() for c in cuerpo["detail"])


def test_moving_a_no_show_says_why():
    from src.modules.competition.domain.services.movimientos_de_partidas import (
        MovimientoImposibleError,
    )
    from src.modules.competition.infrastructure.api.v1.tee_group_routes import (
        _respuesta as respuesta_de_partidas,
    )

    cuerpo = json.loads(
        respuesta_de_partidas(MovimientoImposibleError("PLAYER_IS_NO_SHOW", "x")).body
    )

    assert cuerpo["error_code"] == "PLAYER_IS_NO_SHOW"
    assert cuerpo["detail"] != "PLAYER_IS_NO_SHOW"
