"""
Tests de los argumentos del comando de importación de campos.

Solo cubren la validación de la línea de órdenes: lo que hace el comando con la
base de datos se prueba a través de los casos de uso que invoca.
"""

import argparse

import pytest

from scripts.import_golf_courses import non_negative_int


def test_a_positive_limit_is_accepted():
    """
    GIVEN: Un límite positivo
    WHEN: Se lee el argumento
    THEN: Se convierte en entero
    """
    assert non_negative_int("25") == 25


def test_a_limit_of_zero_is_accepted():
    """
    GIVEN: Un límite de cero
    WHEN: Se lee el argumento
    THEN: Se acepta

    Cero es una pasada en seco que no procesa nada, y es útil para comprobar
    que el volcado se lee sin tocar ningún campo.
    """
    assert non_negative_int("0") == 0


def test_a_negative_limit_is_rejected():
    """
    GIVEN: Un límite negativo
    WHEN: Se lee el argumento
    THEN: Se rechaza al leerlo

    Sin esta comprobación no fallaba: `mapped[:-1]` es una rebanada válida, así
    que la importación se paraba en el primer club y descartaba un recorrido
    sin decir nada.
    """
    with pytest.raises(argparse.ArgumentTypeError, match="must not be negative"):
        non_negative_int("-1")


def test_a_limit_that_is_not_a_number_is_rejected():
    """
    GIVEN: Un límite que no es un entero
    WHEN: Se lee el argumento
    THEN: Se rechaza diciendo qué se ha recibido
    """
    with pytest.raises(argparse.ArgumentTypeError, match="is not an integer"):
        non_negative_int("todos")
