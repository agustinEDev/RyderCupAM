"""
Un evento que un test deja a medio escribir no debe aparecer en la captura del siguiente.

Given un SecurityLogger cuyo hilo tarda en escribir en la salida estándar,
When se vacían los hilos del log (lo que hace el fixture antes de cada test),
Then el evento ya está escrito y nada llega tarde a la captura de después.
"""

import threading
import time

from src.shared.infrastructure.logging import security_logger as modulo
from src.shared.infrastructure.logging.security_logger import SecurityLogger
from tests.unit.shared.infrastructure.logging._hilos_del_log import (
    vacia_todos_los_hilos_del_log,
)


def test_vaciar_los_hilos_espera_al_evento_que_tarda(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(modulo, "_TOPE", modulo.TopeDeSentry())
    monkeypatch.setattr(modulo.sentry_sdk, "capture_message", lambda *_a, **_k: None)
    audit = SecurityLogger(log_dir=tmp_path, log_file="lento.log")
    suelta = threading.Event()
    emit_original = modulo._SalidaEstandar.emit

    def emit_lento(self, record):
        suelta.wait(timeout=5)
        emit_original(self, record)

    monkeypatch.setattr(modulo._SalidaEstandar, "emit", emit_lento)
    try:
        audit.log_login_attempt(
            user_id=None,
            email="lento@example.com",
            success=False,
            failure_reason="x",
            ip_address="203.0.113.7",
            user_agent="ua",
        )
        threading.Timer(0.2, suelta.set).start()

        vacia_todos_los_hilos_del_log()
        capsys.readouterr()  # lo que hace el fixture: descartar lo anterior
        time.sleep(0.4)  # si el evento no estaba escrito, llegaría ahora

        assert capsys.readouterr().out == ""
    finally:
        suelta.set()
        audit.para()
