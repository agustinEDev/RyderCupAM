"""
🎨 Formatters - Formateadores de Logging

Formateador JSON del log de seguridad (JsonFormatter) y su adaptador al
logging estándar de Python (PythonLoggingFormatter).

Características:
- Formateo consistente
- Metadatos enriquecidos
- Correlation IDs
- Contexto de aplicación
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from .config import HandlerConfig


class BaseFormatter(ABC):
    """Formateador base abstracto"""

    def __init__(self, config: HandlerConfig):
        self.config = config
        self.include_correlation_id = config.include_correlation_id
        self.include_context = config.include_context
        self.date_format = config.date_format

    @abstractmethod
    def format(self, record: logging.LogRecord) -> str:
        """Formatea un registro de logging"""
        pass

    def _get_timestamp(self, record: logging.LogRecord) -> str:
        """Obtiene timestamp formateado"""
        dt = datetime.fromtimestamp(record.created)
        return dt.strftime(self.date_format)

    def _extract_extra_data(self, record: logging.LogRecord) -> dict[str, Any]:
        """Extrae datos adicionales del record"""
        extra = {}

        # Campos estándar que ignoramos
        standard_fields = {
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
            "message",
            "exc_info",
            "exc_text",
            "stack_info",
            "getMessage",
        }

        # Extraer campos adicionales
        for key, value in record.__dict__.items():
            if key not in standard_fields:
                extra[key] = value

        return extra


class JsonFormatter(BaseFormatter):
    """
    Formateador JSON estructurado para producción.

    Produce JSON con estructura consistente:
    {
        "timestamp": "2024-11-03T15:30:45.123Z",
        "level": "INFO",
        "logger": "app.users",
        "message": "Usuario registrado",
        "correlation_id": "abc-def",
        "context": {...},
        "extra": {...}
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        """Formatea como JSON estructurado"""
        # Estructura base
        log_entry = {
            "timestamp": self._get_timestamp(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Datos adicionales
        extra = self._extract_extra_data(record)

        # Correlation ID
        if "correlation_id" in extra and self.include_correlation_id:
            log_entry["correlation_id"] = extra.pop("correlation_id")

        # Contexto
        if "context" in extra and self.include_context:
            log_entry["context"] = extra.pop("context")

        # Resto de campos extra
        if extra:
            log_entry["extra"] = extra

        # Información de excepción
        if record.exc_info:
            log_entry["exception"] = logging.Formatter().formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False, separators=(",", ":"))


# Clase para integración con logging estándar de Python
class PythonLoggingFormatter(logging.Formatter):
    """
    Adapter para usar nuestros formatters con el logging estándar de Python.
    """

    def __init__(self, formatter: BaseFormatter):
        super().__init__()
        self.custom_formatter = formatter

    def format(self, record: logging.LogRecord) -> str:
        """Delega el formateo a nuestro formatter personalizado"""
        return self.custom_formatter.format(record)
