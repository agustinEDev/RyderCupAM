"""
La línea JSON del log de seguridad, campo a campo (fase 5, tanda 2 de código muerto).

Fija el formato que escribe el SecurityLogger antes de quitar el andamiaje que lo
montaba (HandlerConfig, BaseFormatter, el adaptador a logging): el formato que se
lee en Render y en el fichero no cambia. El único cambio: sin `extra.taskName`.
"""

import json
import logging
import sys
from datetime import datetime

import pytest

from src.shared.infrastructure.logging.security_logger import SecurityLogger


@pytest.fixture
def formatea(tmp_path):
    """Formatea un registro con el formato que el SecurityLogger pone en sus destinos."""
    audit = SecurityLogger(log_dir=tmp_path, log_file="audit.log")
    destinos = audit._destinos
    try:
        yield lambda record: json.loads(destinos[0].format(record))
    finally:
        audit.para()


def _registro(**extra):
    record = logging.LogRecord(
        name="security_audit",
        level=logging.WARNING,
        pathname="/app/src/modulo.py",
        lineno=42,
        msg="Evento %s",
        args=("raro",),
        exc_info=None,
        func="funcion",
    )
    record.created = 1_762_900_000.25
    for clave, valor in extra.items():
        setattr(record, clave, valor)
    return record


def test_t1_base_fields(formatea):
    """
    Given: Un registro sin datos extra
    When: Se formatea
    Then: Lleva fecha local, nivel, logger, mensaje con sus argumentos, módulo, función y línea
    """
    linea = formatea(_registro())

    assert linea["timestamp"] == datetime.fromtimestamp(1_762_900_000.25).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    assert linea["level"] == "WARNING"
    assert linea["logger"] == "security_audit"
    assert linea["message"] == "Evento raro"
    assert linea["module"] == "modulo"
    assert linea["function"] == "funcion"
    assert linea["line"] == 42


def test_t2_correlation_id_and_context_go_to_the_top_level(formatea):
    """
    Given: Un registro con correlation_id y context
    When: Se formatea
    Then: Los dos suben al primer nivel y no se repiten dentro de extra
    """
    linea = formatea(_registro(correlation_id="abc-123", context={"ip": "1.2.3.4"}))

    assert linea["correlation_id"] == "abc-123"
    assert linea["context"] == {"ip": "1.2.3.4"}
    assert "correlation_id" not in linea.get("extra", {})
    assert "context" not in linea.get("extra", {})


def test_t3_other_fields_go_under_extra(formatea):
    """
    Given: Un registro con campos propios (como el evento de seguridad)
    When: Se formatea
    Then: Van bajo extra, con su valor
    """
    linea = formatea(_registro(security_event={"event_type": "LogoutEvent"}, component="x"))

    assert linea["extra"]["security_event"] == {"event_type": "LogoutEvent"}
    assert linea["extra"]["component"] == "x"


def test_t4_an_exception_is_written_out(formatea):
    """
    Given: Un registro con una excepción
    When: Se formatea
    Then: Lleva la traza en exception
    """
    try:
        raise ValueError("fallo de prueba")
    except ValueError:
        record = _registro(exc_info=sys.exc_info())

    linea = formatea(record)

    assert "ValueError: fallo de prueba" in linea["exception"]
    assert "Traceback" in linea["exception"]


def test_t5_no_extra_key_without_extra_fields(formatea):
    """
    Given: Un registro sin campos propios (y sin el taskName de Python 3.12)
    When: Se formatea
    Then: No hay clave extra ni exception
    """
    record = _registro()
    record.__dict__.pop("taskName", None)

    linea = formatea(record)

    assert "extra" not in linea
    assert "exception" not in linea


def test_t6_the_asyncio_task_name_is_not_written(formatea):
    """
    Given: Un registro con el taskName que Python 3.12+ añade a todos (None fuera de una tarea)
    When: Se formatea
    Then: No aparece: ni extra.taskName ni una clave extra vacía
    """
    linea = formatea(_registro(taskName=None))

    assert "extra" not in linea
