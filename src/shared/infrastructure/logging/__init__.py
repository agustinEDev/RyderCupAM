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
from .logger import Logger, LogLevel
from .config import LogConfig, LogFormat, LogHandler, HandlerConfig
from .factory import LoggerFactory, get_logger, configure_logging
from .python_logger import PythonLogger
from .formatters import FormatterFactory, TextFormatter, JsonFormatter, StructuredFormatter
from .event_handlers import EventLoggingHandler, AuditEventHandler

__all__ = [
    # Core interfaces
    'Logger',
    'LogLevel',
    
    # Configuration
    'LogConfig',
    'LogFormat',
    'LogHandler', 
    'HandlerConfig',
    
    # Factory and convenience functions
    'LoggerFactory',
    'get_logger',
    'configure_logging',
    
    # Implementations
    'PythonLogger',
    
    # Formatters
    'FormatterFactory',
    'TextFormatter',
    'JsonFormatter', 
    'StructuredFormatter',
    
    # Domain Events integration
    'EventLoggingHandler',
    'AuditEventHandler'
]