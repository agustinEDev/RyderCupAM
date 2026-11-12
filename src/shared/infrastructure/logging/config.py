"""
Tipos de configuración de los handlers del log de seguridad: formato
(`LogFormat`), destino (`LogHandler`) y cada handler (`HandlerConfig`).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .logger import LogLevel


class LogFormat(Enum):
    """Formatos de salida disponibles"""

    TEXT = "text"
    JSON = "json"
    STRUCTURED = "structured"


class LogHandler(Enum):
    """Tipos de handlers disponibles"""

    CONSOLE = "console"
    FILE = "file"
    ROTATING_FILE = "rotating_file"
    SYSLOG = "syslog"
    NULL = "null"  # Para tests


@dataclass
class HandlerConfig:
    """Configuración específica de un handler"""

    type: LogHandler
    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.TEXT

    # Configuración específica de archivo
    filename: str | None = None
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5

    # Configuración de formato
    date_format: str = "%Y-%m-%d %H:%M:%S"
    include_correlation_id: bool = True
    include_context: bool = True

    # Configuración adicional
    extra_config: dict[str, Any] = field(default_factory=dict)
