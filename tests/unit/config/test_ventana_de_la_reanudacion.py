"""
La ventana para reanudar una respuesta de refresco perdida se puede ajustar sin desplegar
(B-19 de la auditoría de la fase 6, R5): `REFRESH_RESUME_WINDOW_SECONDS`, 30 minutos por
defecto (Agustín, 15 nov 2026). Un valor que no sea un número positivo, o que pase de una
hora, vuelve a los 30 minutos: nunca «sin límite».
"""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from src.config.dependencies.usuarios import get_refresh_access_token_use_case
from src.config.reanudacion_del_refresco import VENTANA_CONFIGURADA, ventana_de_la_reanudacion


def test_by_default_thirty_minutes(monkeypatch):
    monkeypatch.delenv("REFRESH_RESUME_WINDOW_SECONDS", raising=False)

    assert ventana_de_la_reanudacion() == timedelta(minutes=30)


@pytest.mark.parametrize("segundos", ["300", "3600"])
def test_from_the_environment_up_to_one_hour(monkeypatch, segundos):
    monkeypatch.setenv("REFRESH_RESUME_WINDOW_SECONDS", segundos)

    assert ventana_de_la_reanudacion() == timedelta(seconds=int(segundos))


@pytest.mark.parametrize("valor", ["0", "-5", "abc", "", "3601", "31536000", "100000000000000"])
def test_a_wrong_or_too_large_value_falls_back_to_thirty_minutes(monkeypatch, valor):
    monkeypatch.setenv("REFRESH_RESUME_WINDOW_SECONDS", valor)

    assert ventana_de_la_reanudacion() == timedelta(minutes=30)


def test_the_use_case_gets_the_configured_window():
    """El proveedor monta el caso de uso con la ventana leída al arrancar."""
    caso = get_refresh_access_token_use_case(
        uow=MagicMock(),
        token_service=MagicMock(),
        security_audit=MagicMock(),
        aviso_de_cierre=MagicMock(),
    )

    assert caso._ventana_de_la_reanudacion == VENTANA_CONFIGURADA
