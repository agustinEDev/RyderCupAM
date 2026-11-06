"""
El desbloqueo del administrador también limpia los bloqueos por red (BE #732).

  #   caso                                               | esperado
  ----|---------------------------------------------------|------------------------------
  D1  solo una red bloqueada para la cuenta               | la limpia; el respaldo, intacto
  D2  el respaldo y una red bloqueados                    | limpia los dos
  D3  nada bloqueado                                      | ValueError, como hasta ahora
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from src.config.freno_del_login import FrenoDelLoginEnMemoria
from src.modules.user.application.dto.user_dto import UnlockAccountRequestDTO
from src.modules.user.application.ports.freno_del_login_port import origen_de_red
from src.modules.user.application.use_cases.unlock_account_use_case import UnlockAccountUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio

ANA = "ana.unlock@example.com"
RED_A = origen_de_red("203.0.113.7")


async def _escena(respaldo=False, red=False):
    uow = InMemoryUnitOfWork()
    freno = FrenoDelLoginEnMemoria()
    ana = User.create(
        first_name="Ana", last_name="U", email_str=ANA, plain_password="V@l1dP@ss123!"
    )
    if respaldo:
        for _ in range(50):
            ana.record_failed_login(ahora=datetime.now())
    async with uow:
        await uow.users.save(ana)
    if red:
        for _ in range(10):
            freno.apunta_fallo(ANA, RED_A)
    caso = UnlockAccountUseCase(uow, freno, Mock())
    pide = UnlockAccountRequestDTO(
        user_id=str(ana.id.value), unlocked_by_user_id="5f0c8a2e-1b3d-4e6f-9a7b-2c4d6e8f0a1b"
    )
    return uow, freno, ana, caso, pide


async def test_d1_solo_una_red_bloqueada():
    """
    Given: La red A bloqueada para Ana, sin el respaldo saltado
    When: El administrador la desbloquea
    Then: A queda libre y responde bien
    """
    _uow, freno, _ana, caso, pide = await _escena(red=True)

    r = await caso.execute(pide)

    assert r.success
    assert freno.bloqueado_hasta(ANA, RED_A) is None


async def test_d2_el_respaldo_y_una_red():
    """
    Given: El respaldo de Ana saltado y la red A bloqueada
    When: El administrador la desbloquea
    Then: Los dos quedan libres
    """
    uow, freno, ana, caso, pide = await _escena(respaldo=True, red=True)

    await caso.execute(pide)

    async with uow:
        assert not (await uow.users.find_by_id(ana.id)).is_locked()
    assert freno.bloqueado_hasta(ANA, RED_A) is None


async def test_d3_nada_bloqueado_es_un_error():
    """
    Given: Ana sin nada bloqueado
    When: El administrador la desbloquea
    Then: ValueError, como hasta ahora
    """
    _uow, _freno, _ana, caso, pide = await _escena()

    with pytest.raises(ValueError):
        await caso.execute(pide)
