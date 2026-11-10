"""
El tope global de avisos de fallos (BE #732).

  #   caso                                              | esperado
  ----|-------------------------------------------------|------------------------------
  C1  20 avisos de red en una hora                       | el 21 no cabe
  C2  pasada la hora del primero                         | vuelve a caber uno
  C3  un aviso reservado que no se envió                 | se devuelve: deja hueco
  C4  30 avisos de red en un día (repartidos en horas)   | el 31 no cabe, aunque la hora
                                                         |   tenga hueco
  C5  los avisos graves (aviso, respaldo, dia)           | su propio hueco de 10 al día:
                                                         |   los de red no lo gastan
"""

from datetime import datetime, timedelta

import pytest

from src.config.cupo_de_avisos import (
    AVISOS_DE_RED_POR_DIA,
    AVISOS_DE_RED_POR_HORA,
    AVISOS_GRAVES_POR_DIA,
    CupoDeAvisosEnMemoria,
)


class Reloj:
    def __init__(self):
        self.ahora = datetime(2026, 11, 6, 10, 0)

    def __call__(self):
        return self.ahora


def test_los_numeros():
    """
    Given: El tope de BE #732
    When: Se leen sus constantes
    Then: 20 por hora y 30 al día de red; 10 al día de los graves
    """
    assert (AVISOS_DE_RED_POR_HORA, AVISOS_DE_RED_POR_DIA, AVISOS_GRAVES_POR_DIA) == (20, 30, 10)


def test_c1_c2_veinte_de_red_por_hora():
    """
    Given: El tope de 20 avisos de red por hora
    When: Se reservan 21 seguidos, y otro pasada la hora
    Then: El 21 no cabe; pasada la hora del primero, sí
    """
    reloj = Reloj()
    cupo = CupoDeAvisosEnMemoria(reloj=reloj)

    assert all(cupo.reserva("red") for _ in range(20))
    assert not cupo.reserva("red")
    reloj.ahora += timedelta(hours=1)
    assert cupo.reserva("red")


def test_c3_un_aviso_devuelto_deja_hueco():
    """
    Given: El tope de la hora lleno
    When: Se devuelve un aviso que no se envió
    Then: Cabe otro
    """
    cupo = CupoDeAvisosEnMemoria(reloj=Reloj())
    for _ in range(20):
        cupo.reserva("red")

    cupo.devuelve("red")

    assert cupo.reserva("red")


def test_c4_treinta_de_red_al_dia():
    """
    Given: 30 avisos de red en el día, 10 por hora
    When: Se pide otro en una hora nueva
    Then: No cabe: el día está lleno; al día siguiente, sí
    """
    reloj = Reloj()
    cupo = CupoDeAvisosEnMemoria(reloj=reloj)
    for _ in range(3):
        for _ in range(10):
            assert cupo.reserva("red")
        reloj.ahora += timedelta(hours=1)

    assert not cupo.reserva("red")
    reloj.ahora += timedelta(hours=22)
    assert cupo.reserva("red")


@pytest.mark.parametrize("grave", ["aviso", "respaldo", "dia"])
def test_c5_los_graves_tienen_su_hueco(grave):
    """
    Given: El día de los avisos de red, lleno
    When: Llega un aviso grave
    Then: Cabe: tiene su propio hueco, de 10 al día
    """
    reloj = Reloj()
    cupo = CupoDeAvisosEnMemoria(reloj=reloj)
    for _ in range(3):
        for _ in range(10):
            cupo.reserva("red")
        reloj.ahora += timedelta(hours=1)

    assert all(cupo.reserva(grave) for _ in range(10))
    assert not cupo.reserva(grave)


def test_c6_las_sesiones_cerradas_tienen_su_propio_hueco():
    """
    Given: El aviso de sesión cerrada por seguridad (F-02), que provoca quien tenga una
           cookie robada
    When: Se gastan sus 10 del día
    Then: El 11 no cabe, y ni gasta ni le gastan los de red ni los graves
    """
    from src.config.cupo_de_avisos import AVISOS_DE_SESION_CERRADA_POR_DIA
    from src.modules.user.application.ports.cupo_de_avisos_port import (
        MOTIVO_SESION_CERRADA,
    )

    cupo = CupoDeAvisosEnMemoria(reloj=Reloj())

    assert AVISOS_DE_SESION_CERRADA_POR_DIA == 10
    assert all(cupo.reserva(MOTIVO_SESION_CERRADA) for _ in range(10))
    assert not cupo.reserva(MOTIVO_SESION_CERRADA)
    assert cupo.reserva("respaldo")
    assert cupo.reserva("red")
    cupo.devuelve(MOTIVO_SESION_CERRADA)
    assert cupo.reserva(MOTIVO_SESION_CERRADA)


def test_c6_el_motivo_de_sesion_cerrada_no_cae_en_los_graves():
    """
    Given: Los graves del día ya gastados
    When: Se reserva un aviso de sesión cerrada con la constante del puerto
    Then: Cabe: su motivo existe en el cupo y no cae en el cubo de los graves
    """
    from src.modules.user.application.ports.cupo_de_avisos_port import (
        MOTIVO_SESION_CERRADA,
    )

    cupo = CupoDeAvisosEnMemoria(reloj=Reloj())
    assert all(cupo.reserva("respaldo") for _ in range(AVISOS_GRAVES_POR_DIA))
    assert not cupo.reserva("respaldo")

    assert cupo.reserva(MOTIVO_SESION_CERRADA)
