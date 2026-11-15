"""
La ventana para reanudar una respuesta de refresco perdida se puede ajustar sin desplegar
(B-19 de la auditoría de la fase 6, R5): `REFRESH_RESUME_WINDOW_SECONDS`, 5 minutos por
defecto; un valor que no sea un número positivo vuelve a los 5 minutos, nunca a «sin límite».
"""

from datetime import timedelta

import pytest

from src.config.reanudacion_del_refresco import ventana_de_la_reanudacion


def test_by_default_five_minutes(monkeypatch):
    monkeypatch.delenv("REFRESH_RESUME_WINDOW_SECONDS", raising=False)

    assert ventana_de_la_reanudacion() == timedelta(minutes=5)


def test_from_the_environment(monkeypatch):
    monkeypatch.setenv("REFRESH_RESUME_WINDOW_SECONDS", "900")

    assert ventana_de_la_reanudacion() == timedelta(minutes=15)


@pytest.mark.parametrize("valor", ["0", "-5", "abc", ""])
def test_a_wrong_value_falls_back_to_five_minutes(monkeypatch, valor):
    monkeypatch.setenv("REFRESH_RESUME_WINDOW_SECONDS", valor)

    assert ventana_de_la_reanudacion() == timedelta(minutes=5)


def test_the_use_case_gets_it(monkeypatch):
    monkeypatch.setenv("REFRESH_RESUME_WINDOW_SECONDS", "120")
    import inspect

    from src.config.dependencies import usuarios

    fuente = inspect.getsource(usuarios)
    llamada = fuente[fuente.index("return RefreshAccessTokenUseCase(") :]
    llamada = llamada[: llamada.index("\n    )")]

    assert "ventana_de_la_reanudacion=ventana_de_la_reanudacion()" in llamada
