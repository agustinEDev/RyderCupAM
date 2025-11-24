"""
🎨 Formatters - Formateadores de Logging

Proporciona diferentes formateadores para las salidas de logging:
- TextFormatter: Formato legible para desarrollo
- JsonFormatter: Formato estructurado para producción
- StructuredFormatter: Formato híbrido con contexto

Características:
- Formateo consistente
- Metadatos enriquecidos
- Correlation IDs
- Contexto de aplicación
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Union
from abc import ABC, abstractmethod

from .config import LogFormat, HandlerConfig


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
    
    def _extract_extra_data(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Extrae datos adicionales del record"""
        extra = {}
        
        # Campos estándar que ignoramos
        standard_fields = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
            'filename', 'module', 'lineno', 'funcName', 'created',
            'msecs', 'relativeCreated', 'thread', 'threadName',
            'processName', 'process', 'message', 'exc_info', 'exc_text',
            'stack_info', 'getMessage'
        }
        
        # Extraer campos adicionales
        for key, value in record.__dict__.items():
            if key not in standard_fields:
                extra[key] = value
        
        return extra


class TextFormatter(BaseFormatter):
    """
    Formateador de texto legible para desarrollo.
    
    Produce salidas como:
    2024-11-03 15:30:45 | INFO | app.users | Usuario registrado | user_id=123 correlation_id=abc-def
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Formatea como texto legible"""
        timestamp = self._get_timestamp(record)
        level = record.levelname
        name = record.name
        message = record.getMessage()
        base_msg = f"{timestamp} | {level} | {name} | {message}"
        extra = self._extract_extra_data(record)
        extra_str = self._format_extras(extra)
        if extra_str:
            base_msg += f" | {extra_str}"
        if record.exc_info:
            base_msg += f"\n{logging.Formatter().formatException(record.exc_info)}"
        return base_msg

    def _format_extras(self, extra: dict) -> str:
        extra_parts = []
        # Correlation ID primero si está presente
        if 'correlation_id' in extra and self.include_correlation_id:
            extra_parts.append(f"correlation_id={extra.pop('correlation_id')}")
        # Resto de campos
        if self.include_context:
            for key, value in extra.items():
                if key != 'context':
                    extra_parts.append(f"{key}={value}")
            # Contexto como campos individuales
            if 'context' in extra and isinstance(extra['context'], dict):
                for key, value in extra['context'].items():
                    extra_parts.append(f"{key}={value}")
        return ' '.join(extra_parts) if extra_parts else ''


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
            'timestamp': self._get_timestamp(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Datos adicionales
        extra = self._extract_extra_data(record)
        
        # Correlation ID
        if 'correlation_id' in extra and self.include_correlation_id:
            log_entry['correlation_id'] = extra.pop('correlation_id')
        
        # Contexto
        if 'context' in extra and self.include_context:
            log_entry['context'] = extra.pop('context')
        
        # Resto de campos extra
        if extra:
            log_entry['extra'] = extra
        
        # Información de excepción
        if record.exc_info:
            log_entry['exception'] = logging.Formatter().formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False, separators=(',', ':'))


class StructuredFormatter(BaseFormatter):
    """
    Formateador híbrido que combina legibilidad con estructura.
    
    Produce salidas como:
    [2024-11-03 15:30:45] INFO app.users: Usuario registrado
    ├─ correlation_id: abc-def
    ├─ user_id: 123
    └─ context: {"action": "register"}
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Formatea con estructura híbrida"""
        timestamp = self._get_timestamp(record)
        level = record.levelname
        name = record.name
        message = record.getMessage()
        main_line = f"[{timestamp}] {level} {name}: {message}"
        extra = self._extract_extra_data(record)
        lines = [main_line]
        extra_lines = self._format_structured_extras(extra)
        if extra_lines:
            lines.extend(extra_lines)
        if record.exc_info:
            exc_text = logging.Formatter().formatException(record.exc_info)
            exc_lines = exc_text.split('\n')
            for exc_line in exc_lines:
                if exc_line.strip():
                    lines.append(f"   {exc_line}")
        return '\n'.join(lines)

    def _format_structured_extras(self, extra: dict) -> list:
        extra_lines = []
        if 'correlation_id' in extra and self.include_correlation_id:
            correlation_id = extra.pop('correlation_id')
            extra_lines.append(f"├─ correlation_id: {correlation_id}")
        if self.include_context:
            for key, value in extra.items():
                if key == 'context' and isinstance(value, dict):
                    context_json = json.dumps(value, ensure_ascii=False)
                    extra_lines.append(f"├─ context: {context_json}")
                else:
                    extra_lines.append(f"├─ {key}: {value}")
        if extra_lines:
            extra_lines[-1] = extra_lines[-1].replace('├─', '└─')
        return extra_lines


class FormatterFactory:
    """Factory para crear formatters según configuración"""
    
    @staticmethod
    def create_formatter(config: HandlerConfig) -> BaseFormatter:
        """
        Crea un formatter según la configuración.
        
        Args:
            config: Configuración del handler
            
        Returns:
            Instancia del formatter apropiado
            
        Raises:
            ValueError: Si el formato no es soportado
        """
        if config.format == LogFormat.TEXT:
            return TextFormatter(config)
        elif config.format == LogFormat.JSON:
            return JsonFormatter(config)
        elif config.format == LogFormat.STRUCTURED:
            return StructuredFormatter(config)
        else:
            raise ValueError(f"Formato no soportado: {config.format}")


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