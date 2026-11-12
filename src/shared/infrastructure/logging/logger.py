"""
Niveles de logging del log de seguridad.
"""

from enum import Enum


class LogLevel(Enum):
    """Niveles de logging disponibles"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
