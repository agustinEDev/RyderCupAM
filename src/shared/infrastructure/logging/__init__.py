"""
🏗️ Sistema de Logging - Infraestructura Compartida

Este módulo proporciona una infraestructura de logging avanzada y configurable
para el Ryder Cup Manager, siguiendo principios de Clean Architecture.

Componentes principales:
- Logger: Interface principal para logging
- LogConfig: Configuración centralizada
- Formatters: Formateadores personalizados
- Handlers: Manejadores específicos
- Factory: Creación de loggers configurados

Características:
✅ Logging estructurado (JSON/texto)
✅ Múltiples niveles y handlers
✅ Configuración flexible
✅ Integración con Domain Events
✅ Contexto de correlación
✅ Formateo personalizado
"""

# Re-exportaciones principales
from .config import HandlerConfig, LogConfig, LogFormat, LogHandler
from .event_handlers import AuditEventHandler, EventLoggingHandler
from .factory import LoggerFactory, configure_logging, get_logger
from .formatters import FormatterFactory, JsonFormatter, StructuredFormatter, TextFormatter
from .logger import Logger, LogLevel
from .python_logger import PythonLogger

__all__ = [
    "AuditEventHandler",
    # Domain Events integration
    "EventLoggingHandler",
    # Formatters
    "FormatterFactory",
    "HandlerConfig",
    "JsonFormatter",
    # Configuration
    "LogConfig",
    "LogFormat",
    "LogHandler",
    "LogLevel",
    # Core interfaces
    "Logger",
    # Factory and convenience functions
    "LoggerFactory",
    # Implementations
    "PythonLogger",
    "StructuredFormatter",
    "TextFormatter",
    "configure_logging",
    "get_logger",
]
