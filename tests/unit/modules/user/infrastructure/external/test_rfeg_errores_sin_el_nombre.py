"""
Los errores de la RFEG no llevan el nombre del jugador (revisión de Q-BE-08, 18 nov 2026).

Con una respuesta 4xx/5xx, `httpx.HTTPStatusError` trae la URL de la búsqueda
(`?q=Juan+P%C3%A9rez...`) y su texto pasaba entero al error de dominio, encadenado con
`from e`: cualquier log con `%s` del error o con `exc_info=True` escribía el nombre. El
error de dominio lleva ahora solo el tipo y el código, sin la causa encadenada.

  R1 la RFEG responde 503            -> el error y su traza completa, sin el nombre
  R2 la conexión falla               -> igual
  R3 un log con exc_info=True        -> sin el nombre
"""

import logging
import traceback

import httpx
import pytest

from src.modules.user.domain.errors.handicap_errors import HandicapServiceUnavailableError
from src.modules.user.infrastructure.external import rfeg_handicap_service
from src.modules.user.infrastructure.external.rfeg_handicap_service import RFEGHandicapService

pytestmark = pytest.mark.asyncio

NOMBRE = "Juan Pérez García"
RASTROS = ("Pérez", "P%C3%A9rez", "Juan+P", "Juan%20P", "García", "Garc%C3%ADa")


def _con_respuesta(monkeypatch, manejador):
    cliente_de_verdad = httpx.AsyncClient
    monkeypatch.setattr(
        rfeg_handicap_service.httpx,
        "AsyncClient",
        lambda *a, **kw: cliente_de_verdad(transport=httpx.MockTransport(manejador)),
    )


async def _error_de_la_busqueda() -> HandicapServiceUnavailableError:
    with pytest.raises(HandicapServiceUnavailableError) as capturado:
        await RFEGHandicapService().search_handicap(NOMBRE)
    return capturado.value


def _traza(error: BaseException) -> str:
    return "".join(traceback.format_exception(error))


async def test_r1_a_503_does_not_carry_the_name(monkeypatch):
    """La RFEG responde 503: el error dice el código, nunca el nombre ni la URL."""
    _con_respuesta(monkeypatch, lambda peticion: httpx.Response(503, request=peticion))

    error = await _error_de_la_busqueda()

    traza = _traza(error)
    assert "503" in str(error)
    for rastro in RASTROS:
        assert rastro not in traza, rastro


async def test_r2_a_connection_failure_does_not_carry_the_name(monkeypatch):
    """La conexión falla: tampoco."""

    def falla(peticion):
        # El mensaje original lleva la URL con el nombre: el adaptador tiene que quitarla
        # (CodeRabbit: con «sin red» el test pasaba aunque se copiara el mensaje)
        raise httpx.ConnectError(f"sin red al pedir {peticion.url}", request=peticion)

    _con_respuesta(monkeypatch, falla)

    traza = _traza(await _error_de_la_busqueda())

    for rastro in RASTROS:
        assert rastro not in traza, rastro


async def test_r3_a_log_with_exc_info_does_not_write_the_name(monkeypatch, caplog):
    """Como hacen refresco_rfeg y el refresco del propio hándicap: exc_info=True."""
    _con_respuesta(monkeypatch, lambda peticion: httpx.Response(429, request=peticion))

    with caplog.at_level(logging.WARNING), pytest.raises(HandicapServiceUnavailableError):
        try:
            await RFEGHandicapService().search_handicap(NOMBRE)
        except HandicapServiceUnavailableError:
            logging.getLogger("prueba").warning("RFEG lookup failed", exc_info=True)
            raise

    # El log con la traza se escribió de verdad (CodeRabbit: si la búsqueda devolviera
    # None con un 429, el except no correría y el test pasaría en falso)
    registro = next(r for r in caplog.records if r.name == "prueba")
    assert registro.exc_info is not None
    for rastro in RASTROS:
        assert rastro not in caplog.text, rastro
