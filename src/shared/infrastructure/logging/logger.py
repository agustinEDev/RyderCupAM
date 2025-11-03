"""
🔍 Logger Interface - Contrato Principal de Logging

Define la interfaz principal para el sistema de logging del Ryder Cup Manager.
Proporciona un contrato limpio y flexible para diferentes implementaciones.

Características:
- Interface agnóstica de implementación
- Soporte para logging estructurado
- Contexto y metadatos enriquecidos
- Múltiples niveles de severidad
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
from enum import Enum


class LogLevel(Enum):
    """Niveles de logging disponibles"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Logger(ABC):
    """
    Interface principal para logging en el sistema.
    
    Proporciona un contrato unificado para diferentes implementaciones
    de logging (consola, archivo, estructurado, etc.).
    
    Características:
    - Logging con niveles estándar
    - Contexto y metadatos enriquecidos
    - Soporte para correlation IDs
    - Formateo flexible
    """
    
    @abstractmethod
    def debug(
        self, 
        message: str, 
        extra: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """
        Registra un mensaje de debug.
        
        Args:
            message: Mensaje principal
            extra: Metadatos adicionales
            **kwargs: Argumentos adicionales
        """
        pass
    
    @abstractmethod
    def info(
        self, 
        message: str, 
        extra: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """
        Registra un mensaje informativo.
        
        Args:
            message: Mensaje principal
            extra: Metadatos adicionales
            **kwargs: Argumentos adicionales
        """
        pass
    
    @abstractmethod
    def warning(
        self, 
        message: str, 
        extra: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """
        Registra una advertencia.
        
        Args:
            message: Mensaje principal
            extra: Metadatos adicionales
            **kwargs: Argumentos adicionales
        """
        pass
    
    @abstractmethod
    def error(
        self, 
        message: str, 
        extra: Optional[Dict[str, Any]] = None,
        exc_info: Optional[Union[bool, Exception]] = None,
        **kwargs
    ) -> None:
        """
        Registra un error.
        
        Args:
            message: Mensaje principal
            extra: Metadatos adicionales
            exc_info: Información de excepción
            **kwargs: Argumentos adicionales
        """
        pass
    
    @abstractmethod
    def critical(
        self, 
        message: str, 
        extra: Optional[Dict[str, Any]] = None,
        exc_info: Optional[Union[bool, Exception]] = None,
        **kwargs
    ) -> None:
        """
        Registra un error crítico.
        
        Args:
            message: Mensaje principal
            extra: Metadatos adicionales
            exc_info: Información de excepción
            **kwargs: Argumentos adicionales
        """
        pass
    
    @abstractmethod
    def log(
        self, 
        level: LogLevel, 
        message: str, 
        extra: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """
        Registra un mensaje con nivel específico.
        
        Args:
            level: Nivel de logging
            message: Mensaje principal
            extra: Metadatos adicionales
            **kwargs: Argumentos adicionales
        """
        pass
    
    @abstractmethod
    def set_context(self, context: Dict[str, Any]) -> None:
        """
        Establece contexto global para futuros logs.
        
        Args:
            context: Información de contexto
        """
        pass
    
    @abstractmethod
    def clear_context(self) -> None:
        """Limpia el contexto global"""
        pass
    
    @abstractmethod
    def with_correlation_id(self, correlation_id: str) -> 'Logger':
        """
        Crea un logger con correlation ID específico.
        
        Args:
            correlation_id: ID de correlación
            
        Returns:
            Nueva instancia de logger con correlation ID
        """
        pass