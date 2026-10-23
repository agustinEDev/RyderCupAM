"""El candado de las tareas periódicas nunca vuelve al pool cogido (code-review de la 3b-2, #251)."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.config.candado_de_postgres import soltar

pytestmark = pytest.mark.asyncio


async def test_si_soltarlo_falla_se_cierra_la_conexion():
    candado = AsyncMock()
    candado.scalar.side_effect = RuntimeError("se cayó")

    with pytest.raises(RuntimeError):
        await soltar(candado, 1)

    candado.invalidate.assert_awaited_once()


async def test_si_se_apaga_al_soltarlo_tambien():
    candado = AsyncMock()
    candado.scalar.side_effect = asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await soltar(candado, 1)

    candado.invalidate.assert_awaited_once()


async def test_si_se_suelta_bien_no_se_cierra():
    candado = AsyncMock()

    await soltar(candado, 1)

    candado.commit.assert_awaited_once()
    candado.invalidate.assert_not_awaited()
