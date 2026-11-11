"""
Sistema de Logging - Infraestructura Compartida

La aplicación usa el logging estándar de Python (``logging.getLogger``) y,
para la auditoría, el log de seguridad (``security_logger``).

Componentes:
- LogConfig / HandlerConfig: configuración de los handlers
- JsonFormatter: formato JSON del log de seguridad
- LogLevel: niveles de logging
"""

# Re-exportaciones principales
from .config import HandlerConfig, LogConfig, LogFormat, LogHandler
from .formatters import JsonFormatter
from .logger import LogLevel

__all__ = [
    "HandlerConfig",
    "JsonFormatter",
    "LogConfig",
    "LogFormat",
    "LogHandler",
    "LogLevel",
]
