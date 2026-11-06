"""
Cada desbloqueo queda en el log de seguridad (hotfix 2.50.1, OWASP A09).

El evento AccountUnlockedEvent del dominio no lo leía nadie: el desbloqueo no dejaba
rastro de quién lo hizo, salvo la respuesta HTTP.

  #   caso                                         | esperado
  ----|---------------------------------------------|----------------------------------
  L1  un administrador desbloquea una cuenta        | queda en el log: quién, a quién, desde
      bloqueada por una red (BE #732)               |   dónde y cuántos fallos llevaba
  L2  falla el log                                  | el desbloqueo ya guardado responde bien
  L3  la cuenta no estaba bloqueada                 | ValueError y nada en el log
"""

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

ADMIN = "5f0c8a2e-1b3d-4e6f-9a7b-2c4d6e8f0a1b"


async def _escena(bloqueada=True):
    uow = InMemoryUnitOfWork()
    ana = User.create(
        first_name="Ana",
        last_name="U",
        email_str="ana.l@example.com",
        plain_password="V@l1dP@ss123!",
    )
    freno = FrenoDelLoginEnMemoria()
    if bloqueada:
        # 10 fallos desde una red: la bloquean para Ana (y suman 10 en el respaldo)
        for _ in range(10):
            ana.record_failed_login()
            freno.apunta_fallo("ana.l@example.com", origen_de_red("203.0.113.7"))
    async with uow:
        await uow.users.save(ana)
    auditoria = Mock()
    pide = UnlockAccountRequestDTO(
        user_id=str(ana.id.value),
        unlocked_by_user_id=ADMIN,
        ip_address="203.0.113.7",
        user_agent="Mozilla/5.0 admin",
    )
    return uow, ana, auditoria, UnlockAccountUseCase(uow, freno, auditoria), pide


async def test_l1_el_desbloqueo_queda_en_el_log_de_seguridad():
    """
    Given: Una cuenta bloqueada con 10 fallos
    When: Un administrador la desbloquea
    Then: El log de seguridad recibe quién, a quién, su IP y navegador, y los fallos
    """
    _uow, ana, auditoria, caso, pide = await _escena()

    await caso.execute(pide)

    auditoria.log_account_unlocked.assert_called_once_with(
        user_id=ADMIN,
        unlocked_user_id=str(ana.id.value),
        ip_address="203.0.113.7",
        user_agent="Mozilla/5.0 admin",
        previous_failed_attempts=10,
    )


async def test_l2_un_fallo_del_log_no_deshace_el_desbloqueo(caplog):
    """
    Given: Una cuenta bloqueada, y el log de seguridad falla al escribir
    When: Un administrador la desbloquea
    Then: Responde bien (ya está guardado) y el fallo queda en el log, solo su tipo
    """
    _uow, _ana, auditoria, caso, pide = await _escena()
    auditoria.log_account_unlocked.side_effect = RuntimeError("disco lleno: secreto")

    with caplog.at_level("ERROR"):
        r = await caso.execute(pide)

    assert r.success
    assert "RuntimeError" in caplog.text and "secreto" not in caplog.text


async def test_l3_sin_bloqueo_no_hay_nada_que_apuntar():
    """
    Given: Una cuenta sin bloquear
    When: Un administrador la desbloquea
    Then: ValueError, como siempre, y nada en el log
    """
    _uow, _ana, auditoria, caso, pide = await _escena(bloqueada=False)

    with pytest.raises(ValueError):
        await caso.execute(pide)
    auditoria.log_account_unlocked.assert_not_called()


async def test_l4_sin_ip_ni_navegador_apunta_unknown():
    """
    Given: Un desbloqueo sin IP ni navegador (lo pone la ruta; aquí no llegan)
    When: Se desbloquea
    Then: El log recibe «unknown», como los demás eventos
    """
    _uow, _ana, auditoria, caso, pide = await _escena()
    pide = pide.model_copy(update={"ip_address": None, "user_agent": None})

    await caso.execute(pide)

    kw = auditoria.log_account_unlocked.call_args.kwargs
    assert kw["ip_address"] == "unknown" and kw["user_agent"] == "unknown"
