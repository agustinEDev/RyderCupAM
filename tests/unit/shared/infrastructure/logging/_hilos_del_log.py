"""Vaciado de los hilos del log de seguridad entre tests."""

from src.shared.infrastructure.logging import security_logger as modulo


def vacia_todos_los_hilos_del_log() -> None:
    """Espera a que cada hilo del log haya escrito lo que tenía encolado."""
    with modulo._CERROJO_DE_LAS_ESCUCHAS:
        escuchas = list(modulo._ESCUCHAS.values())
    for escucha in escuchas:
        escucha.stop()
        escucha.start()
