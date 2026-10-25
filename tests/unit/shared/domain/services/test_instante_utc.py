"""
El instante en UTC con su zona, para que el cliente lo ponga en su hora local
(H5, 25 oct 2026). Las fechas de la partida rápida se guardan sin zona (en UTC,
BE #635): sin la zona, `new Date()` del navegador las tomaba como hora local.

| # | entrada                     | sale                         |
|---|-----------------------------|------------------------------|
| I1| sin zona                    | la misma hora, en UTC        |
| I2| con otra zona               | pasada a UTC                 |
| I3| None                        | None                         |
"""

from datetime import UTC, datetime, timedelta, timezone

from src.shared.domain.services.instante_utc import en_utc


def test_i1_sin_zona_es_utc():
    assert en_utc(datetime(2026, 10, 21, 22, 30)) == datetime(2026, 10, 21, 22, 30, tzinfo=UTC)
    assert en_utc(datetime(2026, 10, 21, 22, 30)).tzinfo is UTC


def test_i2_con_otra_zona_se_pasa_a_utc():
    madrid = timezone(timedelta(hours=2))
    resultado = en_utc(datetime(2026, 10, 22, 0, 30, tzinfo=madrid))
    assert resultado == datetime(2026, 10, 21, 22, 30, tzinfo=UTC)
    assert resultado.tzinfo is UTC


def test_i3_none():
    assert en_utc(None) is None
