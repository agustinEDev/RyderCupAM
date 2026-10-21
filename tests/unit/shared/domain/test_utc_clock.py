"""Tests del reloj en UTC sin zona que comparten el dominio y los casos de uso."""

from datetime import UTC, datetime

from src.shared.domain.utc_clock import utc_now


def test_da_la_hora_actual_en_utc_y_sin_zona():
    """
    Given el reloj / When se pide la hora / Then es la de ahora en UTC, sin
    zona: es como se guardan las fechas y como se comparan entre si.
    """
    antes = datetime.now(UTC).replace(tzinfo=None)

    ahora = utc_now()

    despues = datetime.now(UTC).replace(tzinfo=None)
    assert ahora.tzinfo is None
    assert antes <= ahora <= despues
