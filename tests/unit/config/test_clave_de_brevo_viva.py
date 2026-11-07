"""
La clave de Brevo, viva (B1-B3, 7 nov 2026).

Brevo caduca una clave que pasa 90 días sin usarse, y el respaldo se usa poco.

  B1 una consulta al día (estadísticas de los transaccionales), solo en producción,
     enviando por mailgun y con BREVO_API_KEY; nunca en el Kind, en los tests ni sin clave
  B2 si Brevo dice que la clave no vale (401/403): un error propio en Sentry
  B3 otro fallo (caído, red): solo un aviso; se reintenta al día siguiente. Nunca la
     clave ni el cuerpo de la respuesta en el log
"""

import logging

import httpx
import pytest

from src.config.clave_de_brevo_viva import (
    CLAVE_DE_BREVO_RECHAZADA,
    INTERVALO_SEGUNDOS,
    VigiaDeLaClaveDeBrevo,
    vigia_activado,
)
from src.shared.infrastructure.email.envio_de_correo import BrevoTransport


class _Servidor:
    def __init__(self, estado=200, error=None):
        self.estado, self.error, self.peticiones = estado, error, []

    def __call__(self, peticion):
        self.peticiones.append(peticion)
        if self.error:
            raise self.error
        return httpx.Response(self.estado, text='{"detalle":"datos-de-brevo"}')


def _brevo(servidor):
    return BrevoTransport(
        api_key="clave-secreta-brevo",
        api_url="https://api.brevo.com/v3",
        from_email="Ryder Cup Friends <noreply@rydercupfriends.com>",
        transporte_http=httpx.MockTransport(servidor),
    )


PRO = {"ENVIRONMENT": "production", "EMAIL_TRANSPORT": "mailgun", "BREVO_API_KEY": "x"}


@pytest.mark.parametrize(
    ("entorno", "activo"),
    [
        (PRO, True),
        ({**PRO, "EMAIL_TRANSPORT": ""}, True),
        ({**PRO, "ENVIRONMENT": "development"}, False),
        ({**PRO, "EMAIL_TRANSPORT": "mailpit"}, False),
        ({**PRO, "BREVO_API_KEY": ""}, False),
        ({**PRO, "TESTING": "true"}, False),
        ({}, False),
    ],
)
def test_b1_only_in_production_with_mailgun_and_a_key(entorno, activo):
    assert vigia_activado(entorno) is activo


async def test_b1_it_asks_for_yesterdays_transactional_stats():
    servidor = _Servidor(200)

    assert await VigiaDeLaClaveDeBrevo(_brevo(servidor)).vuelta() is True

    (peticion,) = servidor.peticiones
    assert peticion.method == "GET"
    assert peticion.url.path == "/v3/smtp/statistics/aggregatedReport"
    assert peticion.url.params["days"] == "1"
    assert peticion.headers["api-key"] == "clave-secreta-brevo"


async def test_b1_once_a_day_and_a_failing_turn_does_not_stop_it():
    esperas = []

    async def esperar(segundos):
        esperas.append(segundos)
        if len(esperas) == 2:
            raise RuntimeError("fin del test")

    vigia = VigiaDeLaClaveDeBrevo(_brevo(_Servidor(error=ValueError("x"))), esperar=esperar)

    with pytest.raises(RuntimeError, match="fin del test"):
        await vigia.vigilar()

    assert esperas == [INTERVALO_SEGUNDOS, INTERVALO_SEGUNDOS]
    assert INTERVALO_SEGUNDOS == 24 * 60 * 60


@pytest.mark.parametrize("estado", [401, 403])
async def test_b2_a_rejected_key_is_its_own_error(caplog, estado):
    with caplog.at_level(logging.WARNING):
        assert await VigiaDeLaClaveDeBrevo(_brevo(_Servidor(estado))).vuelta() is False

    errores = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert errores == [CLAVE_DE_BREVO_RECHAZADA]
    assert CLAVE_DE_BREVO_RECHAZADA == "Brevo API key rejected"


@pytest.mark.parametrize(
    "servidor",
    [_Servidor(500), _Servidor(429), _Servidor(error=httpx.ConnectError("https://x?k=clave"))],
)
async def test_b3_other_failures_are_only_a_warning(caplog, servidor):
    with caplog.at_level(logging.WARNING):
        assert await VigiaDeLaClaveDeBrevo(_brevo(servidor)).vuelta() is False

    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert "clave-secreta-brevo" not in caplog.text
    assert "datos-de-brevo" not in caplog.text
