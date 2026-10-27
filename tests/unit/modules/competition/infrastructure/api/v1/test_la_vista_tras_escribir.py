"""
La vista de la partida tras anotar, entregar o corregir (27 oct 2026, PR 2).

Quien escribe la recibe con la puerta de una privada: un admin que corrige sin
jugar ni organizar tiene que verla, así que la ruta le dice que es admin.
"""

from uuid import uuid4

import pytest

from src.modules.competition.infrastructure.api.v1.tee_group_scoring_routes import _y_la_vista
from src.modules.user.domain.value_objects.user_id import UserId


class _Ver:
    def __init__(self):
        self.llamadas = []

    async def execute(self, group_id, quien, **kwargs):
        self.llamadas.append(kwargs)
        return "vista"


async def _nada():
    return None


@pytest.mark.parametrize("es_admin", [True, False])
async def test_la_vista_sabe_si_quien_escribe_es_admin(es_admin):
    ver = _Ver()

    vista = await _y_la_vista(_nada(), ver, uuid4(), UserId(uuid4()), es_admin=es_admin)

    assert vista == "vista"
    assert ver.llamadas == [{"es_admin": es_admin}]
