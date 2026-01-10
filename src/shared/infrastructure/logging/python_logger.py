"""
🔧 Python Standard Logger - Implementación Principal

Implementación de la interface Logger usando el sistema de logging estándar
de Python con nuestras extensiones y formatters personalizados.

Características:
- Basado en logging estándar de Python
- Soporte para múltiples handlers
- Contexto y correlation IDs
- Formatters personalizados
- Thread-safe
"""

import logging
import logging.handlers
import sys
import uuid
from contextlib import contextmanager
from threading import local
from typing import Any

from .config import HandlerConfig, LogConfig, LogHandler
from .formatters import FormatterFactory, PythonLoggingFormatter
from .logger import Logger, LogLevel


class PythonLogger(Logger):
    """
    Implementación principal del Logger usando el módulo logging de Python.

    Características:
    - Configuración flexible con múltiples handlers
    - Contexto thread-local
    - Correlation IDs automáticos
    - Formateo personalizado
    - Integración completa con ecosystem Python

    Ejemplo:
        config = LogConfig.development()
        logger = PythonLogger("app.users", config)

        logger.info("Usuario creado", extra={"user_id": 123})

        with logger.correlation_context("req-456"):
            logger.info("Procesando request")
    """

    def __init__(self, name: str, config: LogConfig):
        self.name = name
        self.config = config
        self._python_logger = logging.getLogger(name)
        self._local_context = local()

        # Configurar el logger
        self._setup_logger()

    def _setup_logger(self) -> None:
        """Configura el logger Python con handlers y formatters"""
        # Limpiar handlers existentes
        self._python_logger.handlers.clear()
        self._python_logger.setLevel(self._log_level_to_python(self.config.level))

        # Configurar cada handler
        for handler_config in self.config.handlers:
            handler = self._create_handler(handler_config)
            if handler:
                self._python_logger.addHandler(handler)

        # Evitar propagación a root logger
        self._python_logger.propagate = False

    def _create_handler(self, config: HandlerConfig) -> logging.Handler | None:
        """Crea un handler según la configuración"""
        handler = None

        if config.type == LogHandler.CONSOLE:
            handler = logging.StreamHandler(sys.stdout)

        elif config.type == LogHandler.FILE:
            if config.filename:
                # Crear directorio si no existe
                filepath = self._resolve_log_path(config.filename)
                filepath.parent.mkdir(parents=True, exist_ok=True)
                handler = logging.FileHandler(str(filepath), encoding="utf-8")

        elif config.type == LogHandler.ROTATING_FILE:
            if config.filename:
                filepath = self._resolve_log_path(config.filename)
                filepath.parent.mkdir(parents=True, exist_ok=True)
                handler = logging.handlers.RotatingFileHandler(
                    str(filepath),
                    maxBytes=config.max_bytes,
                    backupCount=config.backup_count,
                    encoding="utf-8",
                )

        elif config.type == LogHandler.NULL:
            handler = logging.NullHandler()

        if handler:
            # Configurar nivel y formatter
            handler.setLevel(self._log_level_to_python(config.level))

            # Crear formatter personalizado
            custom_formatter = FormatterFactory.create_formatter(config)
            python_formatter = PythonLoggingFormatter(custom_formatter)
            handler.setFormatter(python_formatter)

        return handler

    def _resolve_log_path(self, filename: str):
        """Resuelve la ruta completa del archivo de log"""
        from pathlib import Path  # noqa: PLC0415 - Lazy import for method-level usage

        filepath = Path(filename)
        if not filepath.is_absolute() and self.config.log_dir:
            filepath = self.config.log_dir / filename

        return filepath

    def _log_level_to_python(self, level: LogLevel) -> int:
        """Convierte nuestro LogLevel a nivel de Python"""
        mapping = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }
        return mapping[level]

    def _prepare_extra(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """Prepara datos extra con contexto y correlation ID"""
        result = {}

        # Contexto global
        result.update(self.config.default_context)

        # Contexto local del thread
        if hasattr(self._local_context, "context"):
            result.update(self._local_context.context)

        # Correlation ID
        correlation_id = self._get_correlation_id()
        if correlation_id:
            result["correlation_id"] = correlation_id

        # Datos específicos del log
        if extra:
            result.update(extra)

        return result

    def _get_correlation_id(self) -> str | None:
        """Obtiene el correlation ID actual"""
        return getattr(self._local_context, "correlation_id", None)

    def _set_correlation_id(self, correlation_id: str | None) -> None:
        """Establece el correlation ID"""
        self._local_context.correlation_id = correlation_id

    # Implementación de la interface Logger

    def debug(self, message: str, extra: dict[str, Any] | None = None, **kwargs) -> None:
        """Registra un mensaje de debug"""
        prepared_extra = self._prepare_extra(extra)
        self._python_logger.debug(message, extra=prepared_extra, **kwargs)

    def info(self, message: str, extra: dict[str, Any] | None = None, **kwargs) -> None:
        """Registra un mensaje informativo"""
        prepared_extra = self._prepare_extra(extra)
        self._python_logger.info(message, extra=prepared_extra, **kwargs)

    def warning(self, message: str, extra: dict[str, Any] | None = None, **kwargs) -> None:
        """Registra una advertencia"""
        prepared_extra = self._prepare_extra(extra)
        self._python_logger.warning(message, extra=prepared_extra, **kwargs)

    def error(
        self,
        message: str,
        extra: dict[str, Any] | None = None,
        exc_info: bool | Exception | None = None,
        **kwargs,
    ) -> None:
        """Registra un error"""
        prepared_extra = self._prepare_extra(extra)
        self._python_logger.error(message, extra=prepared_extra, exc_info=exc_info, **kwargs)

    def critical(
        self,
        message: str,
        extra: dict[str, Any] | None = None,
        exc_info: bool | Exception | None = None,
        **kwargs,
    ) -> None:
        """Registra un error crítico"""
        prepared_extra = self._prepare_extra(extra)
        self._python_logger.critical(message, extra=prepared_extra, exc_info=exc_info, **kwargs)

    def log(
        self,
        level: LogLevel,
        message: str,
        extra: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """Registra un mensaje con nivel específico"""
        python_level = self._log_level_to_python(level)
        prepared_extra = self._prepare_extra(extra)
        self._python_logger.log(python_level, message, extra=prepared_extra, **kwargs)

    def set_context(self, context: dict[str, Any]) -> None:
        """Establece contexto global para futuros logs"""
        if not hasattr(self._local_context, "context"):
            self._local_context.context = {}
        self._local_context.context.update(context)

    def clear_context(self) -> None:
        """Limpia el contexto global"""
        if hasattr(self._local_context, "context"):
            self._local_context.context.clear()

    def with_correlation_id(self, correlation_id: str) -> "Logger":
        """Crea un logger con correlation ID específico"""
        # Crear una nueva instancia que comparta la configuración
        new_logger = PythonLogger(self.name, self.config)
        new_logger._set_correlation_id(correlation_id)

        # Copiar contexto actual si existe
        if hasattr(self._local_context, "context"):
            new_logger.set_context(self._local_context.context.copy())

        return new_logger

    @contextmanager
    def correlation_context(self, correlation_id: str | None = None):
        """
        Context manager para establecer correlation ID temporalmente.

        Args:
            correlation_id: ID a usar, o None para generar uno automático

        Example:
            with logger.correlation_context("req-123"):
                logger.info("Procesando request")
                # Todos los logs tendrán correlation_id=req-123
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        # Guardar correlation ID anterior
        previous_id = self._get_correlation_id()

        try:
            # Establecer nuevo ID
            self._set_correlation_id(correlation_id)
            yield correlation_id
        finally:
            # Restaurar ID anterior
            self._set_correlation_id(previous_id)

    @contextmanager
    def context(self, **context_data):
        """
        Context manager para establecer contexto temporalmente.

        Example:
            with logger.context(user_id=123, action="create"):
                logger.info("Usuario creado")
                # El log incluirá user_id=123 y action=create
        """
        # Guardar contexto anterior
        previous_context = getattr(self._local_context, "context", {}).copy()

        try:
            # Establecer nuevo contexto
            self.set_context(context_data)
            yield
        finally:
            # Restaurar contexto anterior
            self._local_context.context = previous_context
