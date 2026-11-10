"""
Un evento que otro test dejó a medio escribir no debe aparecer en la captura de este.

Given un SecurityLogger cuyo hilo tarda en escribir en la salida estándar (lo deja un
fixture de módulo, que pytest monta antes que el autouse de la carpeta),
When empieza el test (el fixture autouse ya vació los hilos y descartó la captura),
Then nada llega tarde a su captura.

Protege el fixture entero: si deja de vaciar los hilos o de descartar lo capturado, el
evento aparece aquí.
"""

import threading
import time

import pytest

from src.shared.infrastructure.logging import security_logger as modulo
from src.shared.infrastructure.logging.security_logger import SecurityLogger

_SUELTA_EL_EVENTO_S = 0.2
_MARGEN_PARA_QUE_LLEGUE_TARDE_S = 1.0


@pytest.fixture(scope="module")
def evento_a_medio_escribir(tmp_path_factory):
    suelta = threading.Event()
    emit_original = modulo._SalidaEstandar.emit

    def emit_lento(self, record):
        suelta.wait(timeout=5)
        emit_original(self, record)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(modulo, "_TOPE", modulo.TopeDeSentry())
        mp.setattr(modulo.sentry_sdk, "capture_message", lambda *_a, **_k: None)
        audit = SecurityLogger(log_dir=tmp_path_factory.mktemp("lento"), log_file="lento.log")
        mp.setattr(modulo._SalidaEstandar, "emit", emit_lento)
        audit.log_login_attempt(
            user_id=None,
            email="lento@example.com",
            success=False,
            failure_reason="x",
            ip_address="203.0.113.7",
            user_agent="ua",
        )
        threading.Timer(_SUELTA_EL_EVENTO_S, suelta.set).start()
        try:
            yield
        finally:
            suelta.set()
            audit.para()


def test_nada_de_otro_test_llega_tarde_a_la_captura(evento_a_medio_escribir, capsys):
    time.sleep(_MARGEN_PARA_QUE_LLEGUE_TARDE_S)

    assert capsys.readouterr().out == ""
