"""
El tope diario del formulario de contacto (C4): como mucho 20 mensajes al día en toda
la app, para no gastar el cupo de 100 correos diarios del proveedor.
"""

from datetime import datetime, timedelta

from src.config.cupo_de_contacto import MENSAJES_POR_DIA, CupoDeContactoEnMemoria


class _Reloj:
    def __init__(self):
        self.ahora = datetime(2026, 11, 6, 12, 0)

    def __call__(self):
        return self.ahora


def test_twenty_a_day_then_no_more():
    """
    Given: El tope vacío
    When: Se reservan 21 mensajes el mismo día
    Then: Los 20 primeros caben y el 21 no
    """
    cupo = CupoDeContactoEnMemoria(_Reloj())

    assert MENSAJES_POR_DIA == 20
    assert all(cupo.reserva() for _ in range(20))
    assert cupo.reserva() is False


def test_a_day_later_there_is_room_again():
    """
    Given: El tope lleno
    When: Pasan 24 horas desde el primero
    Then: Vuelve a caber uno
    """
    reloj = _Reloj()
    cupo = CupoDeContactoEnMemoria(reloj)
    for _ in range(20):
        cupo.reserva()

    reloj.ahora += timedelta(hours=24, seconds=1)

    assert cupo.reserva() is True


def test_a_slot_given_back_can_be_used():
    """
    Given: El tope lleno
    When: Se devuelve el último (no salió)
    Then: Cabe otro
    """
    cupo = CupoDeContactoEnMemoria(_Reloj())
    for _ in range(20):
        cupo.reserva()

    cupo.devuelve()

    assert cupo.reserva() is True
