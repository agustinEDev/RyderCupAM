"""
El log de seguridad escribe en un hilo aparte (/code-review de la fase 2, 9 nov 2026).

Cada evento se escribía en stdout y en el fichero dentro de la petición. Ahora el
logger solo encola (QueueHandler) y un QueueListener escribe en su hilo, en orden.
Al cerrar la app (`para`) se escribe lo que quedaba en la cola y lo que llegue
después se escribe directamente: no se pierde nada.
"""

import json

import pytest

from src.shared.domain.events.security_events import LogoutEvent
from src.shared.infrastructure.logging import security_logger as modulo
from src.shared.infrastructure.logging.security_logger import SecurityLogger


@pytest.fixture
def audit(tmp_path, monkeypatch):
    """Un SecurityLogger en una carpeta temporal, sin Sentry; se para al acabar."""
    monkeypatch.setattr(modulo.sentry_sdk, "capture_message", lambda *_a, **_k: None)
    registro = SecurityLogger(log_dir=tmp_path, log_file="audit.log")
    yield registro
    registro.para()


def _salida(numero: int) -> LogoutEvent:
    """Un evento reconocible por su número de tokens revocados."""
    return LogoutEvent(
        user_id="u-1", ip_address="1.2.3.4", user_agent="ua", refresh_tokens_revoked=numero
    )


def _numeros(texto: str) -> list[int]:
    """Los números de los eventos de salida de un texto de líneas JSON, en orden."""
    filas = [json.loads(fila) for fila in texto.splitlines() if fila.strip()]
    return [
        f["extra"]["security_event"]["refresh_tokens_revoked"]
        for f in filas
        if f.get("extra", {}).get("security_event", {}).get("event_type") == "LogoutEvent"
    ]


def test_the_request_only_enqueues(audit):
    """
    Given: Un SecurityLogger
    When: Se miran los handlers de su logger
    Then: Solo una cola: stdout y el fichero los escribe el hilo del QueueListener
    """
    handlers = audit._logger.handlers

    assert audit._encola in handlers
    # Ni stdout ni el fichero cuelgan del logger (pytest puede colgar sus capturas)
    assert not [h for h in handlers if h in audit._destinos]
    assert audit._destinos
    assert audit._escucha._thread is not None and audit._escucha._thread.is_alive()


def test_events_reach_stdout_and_file_in_order(audit, tmp_path, capsys):
    """
    Given: 50 eventos seguidos
    When: Se espera a que el hilo los escriba
    Then: Están todos, en orden, en stdout y en el fichero
    """
    capsys.readouterr()
    for numero in range(50):
        audit.log_security_event(_salida(numero))

    audit.vacia()

    assert _numeros(capsys.readouterr().out) == list(range(50))
    assert _numeros((tmp_path / "audit.log").read_text(encoding="utf-8")) == list(range(50))


def test_stopping_writes_what_was_queued_and_what_comes_after(audit, tmp_path, capsys):
    """
    Given: Eventos encolados
    When: Se para el log (cierre de la app) y después llega otro
    Then: Los encolados quedan escritos y el de después también, directamente
    """
    capsys.readouterr()
    for numero in range(5):
        audit.log_security_event(_salida(numero))

    audit.para()
    audit.log_security_event(_salida(99))

    assert _numeros(capsys.readouterr().out) == [0, 1, 2, 3, 4, 99]
    assert _numeros((tmp_path / "audit.log").read_text(encoding="utf-8")) == [0, 1, 2, 3, 4, 99]


def test_a_new_logger_for_the_same_file_stops_the_previous_thread(tmp_path, monkeypatch):
    """
    Given: Un SecurityLogger de un fichero
    When: Se crea otro para el mismo fichero
    Then: El hilo del primero se para: no quedan hilos huérfanos
    """
    monkeypatch.setattr(modulo.sentry_sdk, "capture_message", lambda *_a, **_k: None)
    primero = SecurityLogger(log_dir=tmp_path, log_file="audit.log")
    hilo = primero._escucha._thread

    segundo = SecurityLogger(log_dir=tmp_path, log_file="audit.log")

    assert hilo is not None and not hilo.is_alive()
    segundo.para()


async def test_the_app_stops_the_log_when_it_shuts_down(monkeypatch):
    """
    Given: La app arrancada (su lifespan)
    When: Se cierra
    Then: Para el log de seguridad, que escribe lo pendiente
    """
    from unittest.mock import Mock

    import main

    registro = Mock()
    monkeypatch.setattr(main, "get_security_logger", lambda: registro)
    monkeypatch.setattr(main, "comprueba_el_envio_de_correo", lambda _entorno: None)
    monkeypatch.setattr(main.settings, "SENTRY_DSN", "")

    async with main.lifespan(main.app):
        registro.para.assert_not_called()

    registro.para.assert_called_once_with()
