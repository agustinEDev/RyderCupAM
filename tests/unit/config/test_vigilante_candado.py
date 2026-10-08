"""El candado del vigilante nunca vuelve al pool cogido (code-review de la 3b-2, #251)."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.config.refresco_de_handicaps import VigilanteDeActualizaciones

pytestmark = pytest.mark.asyncio


async def test_si_soltarlo_falla_se_cierra_la_conexion():
    candado = AsyncMock()
    candado.scalar.side_effect = RuntimeError("se cayó")

    with pytest.raises(RuntimeError):
        await VigilanteDeActualizaciones._soltar(candado)

    candado.invalidate.assert_awaited_once()


async def test_si_se_apaga_al_soltarlo_tambien():
    candado = AsyncMock()
    candado.scalar.side_effect = asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await VigilanteDeActualizaciones._soltar(candado)

    candado.invalidate.assert_awaited_once()


async def test_si_se_suelta_bien_no_se_cierra():
    candado = AsyncMock()

    await VigilanteDeActualizaciones._soltar(candado)

    candado.commit.assert_awaited_once()
    candado.invalidate.assert_not_awaited()
