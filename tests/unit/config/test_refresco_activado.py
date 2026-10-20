"""El refresco con la RFEG solo se enciende en producción, y nunca en los tests (#251)."""

import pytest

from src.config.refresco_de_handicaps import refresco_activado


@pytest.mark.parametrize("valor", ["true", "True", " 1 ", "yes", "on"])
def test_encendido(valor):
    assert refresco_activado({"HANDICAP_REFRESH_ENABLED": valor})


@pytest.mark.parametrize("valor", ["", "false", "0", "no", "off", "si"])
def test_apagado(valor):
    assert not refresco_activado({"HANDICAP_REFRESH_ENABLED": valor})


def test_sin_la_variable_apagado():
    assert not refresco_activado({})


def test_en_los_tests_nunca_aunque_se_encienda():
    assert not refresco_activado({"HANDICAP_REFRESH_ENABLED": "true", "TESTING": "true"})
