"""
Sistema de Logging - Infraestructura Compartida

La aplicación usa el logging estándar de Python (``logging.getLogger``) y,
para la auditoría, el log de seguridad (``security_logger``), que escribe cada
evento como una línea JSON (``JsonFormatter``).
"""

from .formatters import JsonFormatter

__all__ = ["JsonFormatter"]
