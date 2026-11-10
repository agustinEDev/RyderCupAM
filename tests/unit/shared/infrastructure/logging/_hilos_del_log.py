"""Vaciado de los hilos del log de seguridad entre tests."""

from src.shared.infrastructure.logging import security_logger as modulo


def vacia_todos_los_hilos_del_log() -> None:
    """
    Espera a que cada hilo del log en marcha haya escrito lo que tenía encolado.

    Uno ya parado se deja: en Python 3.12, `stop()` sobre él deja un centinela en la
    cola y revienta, y el `start()` siguiente pararía el hilo nuevo al leerlo.
    """
    with modulo._CERROJO_DE_LAS_ESCUCHAS:
        escuchas = list(modulo._ESCUCHAS.values())
    for escucha in escuchas:
        if escucha._thread is None:
            continue
        escucha.stop()
        escucha.start()
