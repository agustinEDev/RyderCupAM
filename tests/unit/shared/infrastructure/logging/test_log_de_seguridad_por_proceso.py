"""
El log de seguridad en los tests (BE #529, 7 nov 2026).

  L1  en los tests, cada proceso de pytest escribe en un fichero propio y vacío al
      empezar: ningún otro proceso lo rota ni escribe en él
  L2  fuera de los tests, el de siempre: logs/security_audit.log
"""

import logging.handlers
from pathlib import Path

from src.shared.infrastructure.logging.security_logger import (
    SecurityLogger,
    get_security_logger,
)


def _fichero_de(registro: SecurityLogger) -> Path:
    """El fichero de su handler rotativo (lo escribe el hilo del log, no el logger)."""
    (handler,) = [
        h for h in registro._destinos if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    return Path(handler.baseFilename)


def test_l1_tests_write_to_their_own_file():
    directorio = get_security_logger().log_dir

    assert directorio != Path("logs")
    assert directorio.is_absolute()
    assert "security_log" in directorio.name


def test_l1_the_handler_points_to_that_file():
    assert _fichero_de(get_security_logger()).parent == get_security_logger().log_dir


def test_l2_outside_the_tests_it_is_the_usual_file():
    assert Path("logs") == SecurityLogger.LOG_DIR
    assert SecurityLogger.LOG_FILE == "security_audit.log"


def test_l1_another_instance_does_not_steal_the_apps_file(tmp_path):
    """Un SecurityLogger de un test (otro fichero) no le quita el suyo al de la app."""
    antes = _fichero_de(get_security_logger())

    otro = SecurityLogger(log_dir=tmp_path, log_file="otro.log")

    assert _fichero_de(get_security_logger()) == antes
    assert _fichero_de(otro) == tmp_path / "otro.log"


def test_l2_the_usual_file_keeps_its_logger_name(tmp_path):
    """El de siempre se sigue llamando security.audit (por si algo lo configura por nombre)."""
    assert (
        SecurityLogger._nombre_del_logger(Path("logs") / "security_audit.log") == "security.audit"
    )
    assert SecurityLogger._nombre_del_logger(tmp_path / "x.log") != "security.audit"


def test_l2_the_usual_file_written_absolute_is_the_same_logger():
    """/code-review: logs/ en absoluto es el mismo fichero, y por tanto el mismo logger
    (si no, dos handlers rotarían el mismo fichero)."""
    absoluta = Path.cwd() / "logs" / "security_audit.log"

    assert SecurityLogger._nombre_del_logger(absoluta) == "security.audit"


def test_l1_a_new_instance_closes_the_handlers_it_replaces(tmp_path):
    """Sin descriptores abiertos de más: al reconfigurar el mismo fichero, el handler
    anterior se cierra."""
    primero = SecurityLogger(log_dir=tmp_path, log_file="x.log")
    handler = _fichero_de_handler(primero)

    SecurityLogger(log_dir=tmp_path, log_file="x.log")

    assert handler.stream is None


def _fichero_de_handler(registro):
    (handler,) = [
        h for h in registro._destinos if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    return handler
