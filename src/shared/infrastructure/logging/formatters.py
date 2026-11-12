"""
Formato JSON del log de seguridad.

Cada registro sale en una línea JSON:
{
    "timestamp": "2026-11-12 04:43:00",
    "level": "INFO",
    "logger": "security_audit",
    "message": "...",
    "module": "...", "function": "...", "line": 42,
    "correlation_id": "...",   # si viene
    "context": {...},          # si viene
    "extra": {...},            # el resto de campos propios del registro
    "exception": "..."         # si hay excepción
}
"""

import json
import logging
from datetime import datetime
from typing import Any

# Atributos que todo LogRecord trae de serie: no son datos del evento.
# `taskName` lo añade Python 3.12+ a todos los registros (None fuera de una tarea).
_CAMPOS_DE_SERIE = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "exc_info",
        "exc_text",
        "stack_info",
    }
)

_FORMATO_DE_FECHA = "%Y-%m-%d %H:%M:%S"


class JsonFormatter(logging.Formatter):
    """Escribe cada registro del log de seguridad como una línea JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Formatea el registro como JSON compacto."""
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).strftime(_FORMATO_DE_FECHA),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        extra = {
            clave: valor
            for clave, valor in record.__dict__.items()
            if clave not in _CAMPOS_DE_SERIE
        }
        if "correlation_id" in extra:
            log_entry["correlation_id"] = extra.pop("correlation_id")
        if "context" in extra:
            log_entry["context"] = extra.pop("context")
        if extra:
            log_entry["extra"] = extra

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False, separators=(",", ":"))
