"""
Reabrir la tarjeta de un no presentado cuando ya juegan 4 (12 oct 2026).

| Caso                              | Respuesta              |
|-----------------------------------|------------------------|
| PartidaLlenaError al reabrir      | 409 GROUP_FULL         |
"""

import json

from src.modules.competition.domain.entities.partida import PartidaLlenaError
from src.modules.competition.infrastructure.api.v1.tee_group_scoring_routes import _respuesta


def test_a_full_group_is_a_conflict():
    respuesta = _respuesta(PartidaLlenaError("llena"))

    assert respuesta.status_code == 409
    assert json.loads(respuesta.body)["error_code"] == "GROUP_FULL"
