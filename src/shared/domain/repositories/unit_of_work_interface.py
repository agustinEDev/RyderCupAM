"""
Unit of Work Interface - Shared Domain Layer

Define el contrato base para el patrón Unit of Work siguiendo principios de Clean Architecture.
Esta interfaz coordina transacciones entre múltiples repositorios manteniendo consistencia.
"""

from abc import ABC, abstractmethod
from typing import AsyncContextManager


class UnitOfWorkInterface(ABC):
    """
    Interfaz base para el patrón Unit of Work.
    
    El Unit of Work mantiene una lista de objetos afectados por una transacción de negocio
    y coordina la escritura de cambios para resolver problemas de concurrencia.
    
    Principios seguidos:
    - Dependency Inversion: El dominio define el contrato, infraestructura lo implementa
    - Single Responsibility: Solo gestión de transacciones y coordinación de repositorios
    - Interface Segregation: Métodos específicos para el ciclo de vida transaccional
    
    Uso típico:
    ```python
    async with unit_of_work:
        user = await unit_of_work.users.find_by_id(user_id)
        user.update_name("New Name")
        await unit_of_work.users.save(user)
        await unit_of_work.commit()
    ```
    """

    @abstractmethod
    async def __aenter__(self):
        """
        Inicia una nueva unidad de trabajo (contexto async).
        
        Se llama automáticamente cuando se entra en el bloque 'async with'.
        Debe configurar la sesión/conexión de base de datos y preparar los repositorios.
        
        Returns:
            UnitOfWorkInterface: La instancia del Unit of Work
        """
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Finaliza la unidad de trabajo (contexto async).
        
        Se llama automáticamente al salir del bloque 'async with'.
        Si hay una excepción, debe hacer rollback; si no, debe hacer commit automático.
        
        Args:
            exc_type: Tipo de excepción si ocurrió una
            exc_val: Valor de la excepción si ocurrió una
            exc_tb: Traceback de la excepción si ocurrió una
        """
        pass

    @abstractmethod
    async def commit(self) -> None:
        """
        Confirma todas las operaciones pendientes de la unidad de trabajo.
        
        Ejecuta todas las operaciones de escritura (INSERT, UPDATE, DELETE) 
        que han sido acumuladas durante la transacción.
        
        Raises:
            UnitOfWorkError: Si ocurre un error durante el commit
            RepositoryError: Si hay errores de persistencia
        """
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """
        Revierte todas las operaciones pendientes de la unidad de trabajo.
        
        Deshace todos los cambios que no han sido confirmados y restaura
        el estado anterior de la base de datos.
        
        Raises:
            UnitOfWorkError: Si ocurre un error durante el rollback
        """
        pass

    @abstractmethod
    async def flush(self) -> None:
        """
        Sincroniza el estado de los objetos con la base de datos sin hacer commit.
        
        Ejecuta las operaciones SQL pero no confirma la transacción.
        Útil para obtener IDs generados o validar constraints antes del commit final.
        
        Raises:
            UnitOfWorkError: Si ocurre un error durante el flush
            RepositoryError: Si hay errores de persistencia
        """
        pass

    @abstractmethod
    def is_active(self) -> bool:
        """
        Verifica si la unidad de trabajo está actualmente activa.
        
        Returns:
            bool: True si hay una transacción activa, False si no
        """
        pass