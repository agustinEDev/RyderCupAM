"""
⚙️ Configuración de Logging - LogConfig

Proporciona configuración centralizada y flexible para el sistema de logging.
Soporta múltiples formatos, handlers y niveles de configuración.

Características:
- Configuración por archivos y código
- Múltiples handlers simultáneos
- Formateo personalizable
- Configuración por entorno
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
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


@dataclass
class LogConfig:
    """
    Configuración principal del sistema de logging.

    Permite configurar múltiples handlers con diferentes niveles,
    formatos y destinos de salida.

    Ejemplos:
        # Configuración básica
        config = LogConfig(
            level=LogLevel.INFO,
            handlers=[
                HandlerConfig(type=LogHandler.CONSOLE),
                HandlerConfig(
                    type=LogHandler.FILE,
                    filename="app.log"
                )
            ]
        )

        # Configuración avanzada
        config = LogConfig.from_dict({
            "level": "DEBUG",
            "handlers": [
                {
                    "type": "console",
                    "format": "json"
                },
                {
                    "type": "rotating_file",
                    "filename": "logs/app.log",
                    "max_bytes": 50000000,
                    "backup_count": 10
                }
            ]
        })
    """

    # Configuración global
    level: LogLevel = LogLevel.INFO
    handlers: list[HandlerConfig] = field(default_factory=list)

    # Configuración de aplicación
    app_name: str = "ryder-cup-manager"
    version: str = "1.0.0"
    environment: str = "development"

    # Configuración de contexto
    default_context: dict[str, Any] = field(default_factory=dict)
    correlation_id_header: str = "X-Correlation-ID"

    # Configuración de formateo
    message_template: str = "{timestamp} | {level} | {name} | {message}"
    json_indent: int | None = None

    # Configuración de directorios
    log_dir: Path | None = None

    def __post_init__(self):
        """Validación y configuración por defecto"""
        if not self.handlers:
            # Handler por defecto: consola
            self.handlers = [HandlerConfig(type=LogHandler.CONSOLE)]

        if self.log_dir:
            self.log_dir = Path(self.log_dir)
            self.log_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "LogConfig":
        """
        Crea configuración desde diccionario.

        Args:
            config_dict: Diccionario de configuración

        Returns:
            Instancia configurada
        """
        # Convertir level si es string
        if "level" in config_dict and isinstance(config_dict["level"], str):
            config_dict["level"] = LogLevel(config_dict["level"].upper())

        # Convertir handlers
        if "handlers" in config_dict:
            handlers = []
            for handler_dict in config_dict["handlers"]:
                handler_config = cls._handler_from_dict(handler_dict)
                handlers.append(handler_config)
            config_dict["handlers"] = handlers

        return cls(**config_dict)

    @classmethod
    def _handler_from_dict(cls, handler_dict: dict[str, Any]) -> HandlerConfig:
        """Convierte diccionario en HandlerConfig"""
        # Convertir enums si son strings
        if "type" in handler_dict and isinstance(handler_dict["type"], str):
            handler_dict["type"] = LogHandler(handler_dict["type"].lower())

        if "level" in handler_dict and isinstance(handler_dict["level"], str):
            handler_dict["level"] = LogLevel(handler_dict["level"].upper())

        if "format" in handler_dict and isinstance(handler_dict["format"], str):
            handler_dict["format"] = LogFormat(handler_dict["format"].lower())

        return HandlerConfig(**handler_dict)

    @classmethod
    def development(cls) -> "LogConfig":
        """Configuración optimizada para desarrollo"""
        return cls(
            level=LogLevel.DEBUG,
            environment="development",
            handlers=[
                HandlerConfig(
                    type=LogHandler.CONSOLE, level=LogLevel.DEBUG, format=LogFormat.TEXT
                )
            ],
        )

    @classmethod
    def production(cls) -> "LogConfig":
        """Configuración optimizada para producción"""
        return cls(
            level=LogLevel.INFO,
            environment="production",
            handlers=[
                HandlerConfig(
                    type=LogHandler.CONSOLE,
                    level=LogLevel.WARNING,
                    format=LogFormat.JSON,
                ),
                HandlerConfig(
                    type=LogHandler.ROTATING_FILE,
                    level=LogLevel.INFO,
                    format=LogFormat.JSON,
                    filename="logs/app.log",
                    max_bytes=50 * 1024 * 1024,  # 50MB
                    backup_count=10,
                ),
            ],
        )

    @classmethod
    def testing(cls) -> "LogConfig":
        """Configuración optimizada para tests"""
        return cls(
            level=LogLevel.WARNING,
            environment="testing",
            handlers=[HandlerConfig(type=LogHandler.NULL, level=LogLevel.CRITICAL)],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convierte la configuración a diccionario"""
        result = {
            "level": self.level.value,
            "app_name": self.app_name,
            "version": self.version,
            "environment": self.environment,
            "default_context": self.default_context,
            "correlation_id_header": self.correlation_id_header,
            "message_template": self.message_template,
            "json_indent": self.json_indent,
            "handlers": [],
        }

        for handler in self.handlers:
            handler_dict = {
                "type": handler.type.value,
                "level": handler.level.value,
                "format": handler.format.value,
                "filename": handler.filename,
                "max_bytes": handler.max_bytes,
                "backup_count": handler.backup_count,
                "date_format": handler.date_format,
                "include_correlation_id": handler.include_correlation_id,
                "include_context": handler.include_context,
                "extra_config": handler.extra_config,
            }
            result["handlers"].append(handler_dict)

        if self.log_dir:
            result["log_dir"] = str(self.log_dir)

        return result
