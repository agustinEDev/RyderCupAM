"""El refresco del hándicap con la RFEG antes de usarlo en una competición.

Vivía dentro de la generación de partidos (HM-1a). Sale a su propio servicio
porque el stroke play lo necesita también al fijar la categoría de cada jugador
(RyderCupAM#251), con las mismas reglas: solo en España, como mucho una vez al
día, y sin bloquear nunca lo que se está haciendo.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.competition.application.services.refresco_rfeg import RefrescoRfeg


def _jugador(pais: str | None = "ES", actualizado: datetime | None = None):
    jugador = MagicMock()
    jugador.country_code = None if pais is None else MagicMock(value=pais)
    jugador.handicap_updated_at = actualizado
    jugador.get_full_name.return_value = "Jaime Ortega"
    return jugador


def _servicio(respuesta=12.3, falla: bool = False):
    servicio = MagicMock()
    servicio.search_handicap = AsyncMock(
        side_effect=ConnectionError("RFEG caída") if falla else None, return_value=respuesta
    )
    return servicio


def _repositorio(falla: bool = False):
    repo = MagicMock()
    repo.save = AsyncMock(side_effect=RuntimeError("BD caída") if falla else None)
    return repo


@pytest.mark.asyncio
class TestRefrescoRfeg:
    async def test_un_jugador_espanol_sin_refrescar_hoy_se_actualiza_y_se_guarda(self):
        jugador, servicio, repo = _jugador(), _servicio(12.3), _repositorio()

        await RefrescoRfeg(servicio, repo).si_toca(jugador)

        servicio.search_handicap.assert_awaited_once_with("Jaime Ortega")
        jugador.update_handicap.assert_called_once_with(12.3)
        repo.save.assert_awaited_once_with(jugador)

    async def test_si_lo_refresco_ayer_tambien(self):
        jugador = _jugador(actualizado=datetime.now(UTC) - timedelta(days=1))
        servicio = _servicio()

        await RefrescoRfeg(servicio, _repositorio()).si_toca(jugador)

        servicio.search_handicap.assert_awaited_once()

    @pytest.mark.parametrize("pais", ["FR", None])
    async def test_fuera_de_espana_no_se_pregunta(self, pais):
        servicio = _servicio()

        await RefrescoRfeg(servicio, _repositorio()).si_toca(_jugador(pais=pais))

        servicio.search_handicap.assert_not_awaited()

    async def test_si_ya_se_refresco_hoy_no_se_pregunta_otra_vez(self):
        servicio = _servicio()

        await RefrescoRfeg(servicio, _repositorio()).si_toca(
            _jugador(actualizado=datetime.now(UTC))
        )

        servicio.search_handicap.assert_not_awaited()

    async def test_sin_servicio_de_la_rfeg_no_hace_nada(self):
        jugador = _jugador()

        await RefrescoRfeg(None, _repositorio()).si_toca(jugador)

        jugador.update_handicap.assert_not_called()

    async def test_si_la_rfeg_falla_se_sigue_sin_tocar_nada(self):
        jugador, repo = _jugador(), _repositorio()

        await RefrescoRfeg(_servicio(falla=True), repo).si_toca(jugador)

        jugador.update_handicap.assert_not_called()
        repo.save.assert_not_awaited()

    async def test_si_la_rfeg_no_lo_encuentra_no_se_toca(self):
        jugador, repo = _jugador(), _repositorio()

        await RefrescoRfeg(_servicio(respuesta=None), repo).si_toca(jugador)

        jugador.update_handicap.assert_not_called()
        repo.save.assert_not_awaited()

    async def test_si_falla_el_guardado_tampoco_se_rompe_nada(self):
        jugador = _jugador()

        await RefrescoRfeg(_servicio(), _repositorio(falla=True)).si_toca(jugador)

        jugador.update_handicap.assert_called_once_with(12.3)
