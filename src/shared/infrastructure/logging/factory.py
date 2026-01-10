"""
🏭 Logger Factory - Creación y Gestión de Loggers

Factory centralizado para crear y gestionar instancias de loggers
con configuración consistente en toda la aplicación.

Características:
- Creación centralizada de loggers
- Configuración por defecto y personalizada
- Cache de instancias
- Configuración por archivos
- Singleton para gestión global
"""

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Optional

from .config import LogConfig
from .logger import Logger
from .python_logger import PythonLogger


class LoggerFactory:
    """
    Factory para crear y gestionar loggers de manera centralizada.

    Características:
    - Singleton para configuración global
    - Cache de loggers por nombre
    - Configuración desde archivos
    - Configuración por entorno
    - Thread-safe

    Ejemplos:
        # Configuración básica
        factory = LoggerFactory()
        logger = factory.get_logger("app.users")

        # Configuración personalizada
        config = LogConfig.production()
        factory = LoggerFactory(config)
        logger = factory.get_logger("app.events")

        # Desde archivo de configuración
        factory = LoggerFactory.from_file("config/logging.yaml")
        logger = factory.get_logger("app.api")
    """

    _instance: Optional["LoggerFactory"] = None
    _lock = Lock()

    def __init__(self, config: LogConfig | None = None):
        self.config = config or self._get_default_config()
        self._loggers: dict[str, Logger] = {}
        self._logger_lock = Lock()

    def __new__(cls, config: LogConfig | None = None):  # noqa: ARG004
        """Implementación singleton thread-safe"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Resetea la instancia singleton (útil para tests)"""
        with cls._lock:
            cls._instance = None

    def get_logger(self, name: str) -> Logger:
        """
        Obtiene un logger por nombre, creándolo si es necesario.

        Args:
            name: Nombre del logger (ej: "app.users", "api.auth")

        Returns:
            Instancia de logger configurada
        """
        with self._logger_lock:
            if name not in self._loggers:
                self._loggers[name] = self._create_logger(name)
            return self._loggers[name]

    def _create_logger(self, name: str) -> Logger:
        """Crea una nueva instancia de logger"""
        return PythonLogger(name, self.config)

    def update_config(self, config: LogConfig) -> None:
        """
        Actualiza la configuración y recrea todos los loggers.

        Args:
            config: Nueva configuración
        """
        with self._logger_lock:
            self.config = config
            # Recrear todos los loggers con nueva configuración
            for name in self._loggers:
                self._loggers[name] = self._create_logger(name)

    def clear_loggers(self) -> None:
        """Limpia todos los loggers cacheados"""
        with self._logger_lock:
            self._loggers.clear()

    @classmethod
    def from_file(cls, config_path: str | Path) -> "LoggerFactory":
        """
        Crea factory desde archivo de configuración.

        Args:
            config_path: Ruta al archivo de configuración (JSON o YAML)

        Returns:
            Instancia configurada

        Raises:
            FileNotFoundError: Si el archivo no existe
            ValueError: Si el formato no es válido
        """
        if not isinstance(config_path, Path):
            config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(
                f"Archivo de configuración no encontrado: {config_path}"
            )

        # Cargar según extensión
        if config_path.suffix.lower() in [".yaml", ".yml"]:
            config_dict = cls._load_yaml(config_path)
        elif config_path.suffix.lower() == ".json":
            config_dict = cls._load_json(config_path)
        else:
            raise ValueError(f"Formato no soportado: {config_path.suffix}")

        config = LogConfig.from_dict(config_dict)
        return cls(config)

    @classmethod
    def from_environment(cls) -> "LoggerFactory":
        """
        Crea factory basado en variables de entorno.

        Variables soportadas:
        - LOG_LEVEL: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        - LOG_FORMAT: Formato (text, json, structured)
        - LOG_FILE: Archivo de log
        - ENVIRONMENT: Entorno (development, production, testing)

        Returns:
            Instancia configurada según entorno
        """
        env = os.getenv("ENVIRONMENT", "development").lower()

        # Configuración base según entorno
        if env == "production":
            config = LogConfig.production()
        elif env == "testing":
            config = LogConfig.testing()
        else:
            config = LogConfig.development()

        # Personalizar según variables de entorno
        if log_level := os.getenv("LOG_LEVEL"):
            from .logger import (  # noqa: PLC0415
                LogLevel,
            )

            config.level = LogLevel(log_level.upper())

        if log_file := os.getenv("LOG_FILE"):
            from .config import (  # noqa: PLC0415
                HandlerConfig,
                LogHandler,
            )

            file_handler = HandlerConfig(
                type=LogHandler.ROTATING_FILE, filename=log_file
            )
            config.handlers.append(file_handler)

        if log_format := os.getenv("LOG_FORMAT"):
            from .config import (  # noqa: PLC0415
                LogFormat,
            )

            for handler in config.handlers:
                handler.format = LogFormat(log_format.lower())

        return cls(config)

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        """Carga archivo YAML"""
        try:
            import yaml  # noqa: PLC0415 - Optional dependency, lazy import

            with open(path, encoding="utf-8") as f:  # noqa: PTH123
                return yaml.safe_load(f) or {}
        except ImportError as e:
            raise ImportError(
                "PyYAML no está instalado. Instálalo con: pip install pyyaml"
            ) from e

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        """Carga archivo JSON"""
        with open(path, encoding="utf-8") as f:  # noqa: PTH123
            return json.load(f)

    def _get_default_config(self) -> LogConfig:
        """Obtiene configuración por defecto según entorno"""
        env = os.getenv("ENVIRONMENT", "development").lower()

        if env == "production":
            return LogConfig.production()
        if env == "testing":
            return LogConfig.testing()
        return LogConfig.development()

    def get_config(self) -> LogConfig:
        """Obtiene la configuración actual"""
        return self.config

    def list_loggers(self) -> dict[str, Logger]:
        """Lista todos los loggers creados"""
        with self._logger_lock:
            return self._loggers.copy()


# Funciones de conveniencia globales
_default_factory: LoggerFactory | None = None


def get_logger(name: str) -> Logger:
    """
    Función de conveniencia para obtener un logger.

    Args:
        name: Nombre del logger

    Returns:
        Instancia de logger
    """
    global _default_factory  # noqa: PLW0603 - Module-level singleton pattern
    if _default_factory is None:
        _default_factory = LoggerFactory()
    return _default_factory.get_logger(name)


def configure_logging(config: LogConfig) -> None:
    """
    Configura el sistema de logging globalmente.

    Args:
        config: Configuración de logging
    """
    global _default_factory  # noqa: PLW0603 - Module-level singleton pattern
    _default_factory = LoggerFactory(config)


def configure_from_file(config_path: str | Path) -> None:
    """
    Configura el sistema de logging desde archivo.

    Args:
        config_path: Ruta al archivo de configuración
    """
    global _default_factory  # noqa: PLW0603 - Module-level singleton pattern
    _default_factory = LoggerFactory.from_file(config_path)


def configure_from_environment() -> None:
    """Configura el sistema de logging desde variables de entorno"""
    global _default_factory  # noqa: PLW0603 - Module-level singleton pattern
    _default_factory = LoggerFactory.from_environment()


def reset_logging() -> None:
    """Resetea la configuración de logging (útil para tests)"""
    global _default_factory  # noqa: PLW0603 - Module-level singleton pattern
    _default_factory = None
    LoggerFactory.reset_instance()
