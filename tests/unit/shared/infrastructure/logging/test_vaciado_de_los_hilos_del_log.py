"""
El vaciado de los hilos del log entre tests aguanta un hilo ya parado.

En Python 3.12, `QueueListener.stop()` sobre uno ya parado deja un centinela en la cola
y revienta (`_thread` es None): el fixture fallaría y el siguiente `start()` pararía el
hilo nuevo nada más leer ese centinela.
"""

from src.shared.infrastructure.logging import security_logger as modulo
from src.shared.infrastructure.logging.security_logger import SecurityLogger
from tests.unit.shared.infrastructure.logging._hilos_del_log import (
    vacia_todos_los_hilos_del_log,
)


def test_a_stopped_listener_is_left_alone(tmp_path, monkeypatch):
    """
    Given: Un hilo del log ya parado que sigue en la lista de hilos
    When: Se vacían todos los hilos
    Then: No revienta, no deja nada en su cola y sigue parado
    """
    monkeypatch.setattr(modulo.sentry_sdk, "capture_message", lambda *_a, **_k: None)
    audit = SecurityLogger(log_dir=tmp_path, log_file="parado.log")
    escucha = audit._escucha
    escucha.stop()
    try:
        vacia_todos_los_hilos_del_log()

        assert escucha.queue.empty()
        assert escucha._thread is None
    finally:
        # Para cerrarlo como los demás, en marcha (`para` lo detiene)
        if escucha._thread is None:
            escucha.start()
        audit.para()


def test_a_running_listener_is_flushed_and_keeps_running(tmp_path, monkeypatch):
    """
    Given: Un hilo del log en marcha con un evento encolado
    When: Se vacían todos los hilos
    Then: El evento está escrito y el hilo sigue en marcha
    """
    monkeypatch.setattr(modulo.sentry_sdk, "capture_message", lambda *_a, **_k: None)
    audit = SecurityLogger(log_dir=tmp_path, log_file="vivo.log")
    try:
        audit.log_logout(user_id="u", ip_address="1.2.3.4", user_agent="ua")

        vacia_todos_los_hilos_del_log()

        assert "LogoutEvent" in (tmp_path / "vivo.log").read_text(encoding="utf-8")
        assert audit._escucha._thread is not None and audit._escucha._thread.is_alive()
    finally:
        audit.para()
