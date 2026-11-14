"""
Un 5xx no le cuenta al cliente qué ha fallado por dentro (auditoría de la fase 6,
B-15 = Q-BE F-06).

    caso                                           | respuesta
    -----------------------------------------------|------------------------------------
    E1 roles: falla la base de datos               | 500 «Internal server error», sin más
    E1b roles: el detalle sí queda en el log       | logger.exception con la causa
    E2 hándicap: la RFEG no responde               | 503 sin el error de la conexión
    E3 roles: competición que no existe (sin cambio)| 404 como siempre
"""

import logging
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.modules.user.domain.errors.handicap_errors import HandicapServiceUnavailableError
from src.modules.user.infrastructure.api.v1.handicap_routes import (
    UpdateHandicapRequestDTO,
    update_user_handicap,
)
from src.modules.user.infrastructure.api.v1.user_routes import get_my_roles_in_competition

SECRETO = "connection to 10.0.0.5:5432 failed for user rydercup_owner"


def _usuario(admin: bool = False) -> MagicMock:
    usuario = MagicMock()
    usuario.id = uuid4()
    usuario.is_admin = admin
    return usuario


def _uow_que_falla(error: Exception) -> MagicMock:
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.competitions.find_by_id = AsyncMock(side_effect=error)
    return uow


@pytest.mark.asyncio
async def test_e1_el_500_de_los_roles_no_lleva_el_texto_del_error():
    with pytest.raises(HTTPException) as fallo:
        await get_my_roles_in_competition(
            competition_id=uuid4(),
            current_user=_usuario(),
            uow=_uow_que_falla(RuntimeError(SECRETO)),
        )

    assert fallo.value.status_code == 500
    assert fallo.value.detail == "Internal server error"


@pytest.mark.asyncio
async def test_e1b_el_detalle_del_500_queda_en_el_log(caplog):
    caplog.set_level(logging.ERROR)

    with pytest.raises(HTTPException):
        await get_my_roles_in_competition(
            competition_id=uuid4(),
            current_user=_usuario(),
            uow=_uow_que_falla(RuntimeError(SECRETO)),
        )

    registro = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert registro, "el fallo interno tiene que quedar en el log"
    assert any(r.exc_info and SECRETO in str(r.exc_info[1]) for r in registro)


@pytest.mark.asyncio
async def test_e2_el_503_del_handicap_no_lleva_el_error_de_la_rfeg():
    usuario = _usuario(admin=True)
    caso_de_uso = MagicMock()
    caso_de_uso.execute = AsyncMock(
        side_effect=HandicapServiceUnavailableError(
            f"Error de conexión con el servicio RFEG: {SECRETO}"
        )
    )

    # La función de debajo del limitador: el decorador exige una petición real
    ruta = getattr(update_user_handicap, "__wrapped__", update_user_handicap)
    with pytest.raises(HTTPException) as fallo:
        await ruta(
            request=MagicMock(),
            handicap_data=UpdateHandicapRequestDTO(user_id=uuid4()),
            use_case=caso_de_uso,
            current_user=usuario,
        )

    assert fallo.value.status_code == 503
    assert fallo.value.detail == "El servicio de hándicap no está disponible"


@pytest.mark.asyncio
async def test_e3_una_competicion_que_no_existe_sigue_dando_404():
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.competitions.find_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as fallo:
        await get_my_roles_in_competition(competition_id=uuid4(), current_user=_usuario(), uow=uow)

    assert fallo.value.status_code == 404
