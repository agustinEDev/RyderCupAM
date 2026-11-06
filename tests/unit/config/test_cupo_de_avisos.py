"""
El tope global de avisos de fallos (BE #732).

  #   caso                                   | esperado
  ----|---------------------------------------|----------------------------
  C1  20 avisos en una hora                   | el 21 no cabe
  C2  pasada la hora del primero              | vuelve a caber uno
  C3  un aviso reservado que no se envió      | se devuelve: deja hueco
"""

from datetime import datetime, timedelta

from src.config.cupo_de_avisos import AVISOS_POR_HORA, CupoDeAvisosEnMemoria


class Reloj:
    def __init__(self):
        self.ahora = datetime(2026, 11, 6, 10, 0)

    def __call__(self):
        return self.ahora


def test_c1_c2_veinte_por_hora():
    """
    Given: El tope de 20 por hora
    When: Se reservan 21 seguidos, y otro pasada la hora
    Then: El 21 no cabe; pasada la hora del primero, sí
    """
    reloj = Reloj()
    cupo = CupoDeAvisosEnMemoria(reloj=reloj)

    assert AVISOS_POR_HORA == 20
    assert all(cupo.reserva() for _ in range(20))
    assert not cupo.reserva()
    reloj.ahora += timedelta(hours=1)
    assert cupo.reserva()


def test_c3_un_aviso_devuelto_deja_hueco():
    """
    Given: El tope lleno
    When: Se devuelve un aviso que no se envió
    Then: Cabe otro
    """
    cupo = CupoDeAvisosEnMemoria(reloj=Reloj())
    for _ in range(20):
        cupo.reserva()

    cupo.devuelve()

    assert cupo.reserva()
