"""
User Repository Interface - Domain Layer

Define el contrato para la persistencia de usuarios siguiendo principios de Clean Architecture.
Esta interfaz pertenece al dominio y será implementada en la capa de infraestructura.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from ..entities.user import User
from ..value_objects.user_id import UserId
from ..value_objects.email import Email


class UserRepositoryInterface(ABC):
    """
    Interfaz para el repositorio de usuarios.
    
    Define las operaciones básicas CRUD y consultas específicas del dominio de usuarios.
    Esta interfaz es independiente de la implementación de persistencia concreta.
    
    Principios seguidos:
    - Dependency Inversion: El dominio define el contrato, infraestructura lo implementa
    - Single Responsibility: Solo operaciones relacionadas con persistencia de users
    - Interface Segregation: Métodos específicos y cohesivos
    """

    @abstractmethod
    async def save(self, user: User) -> None:
        """
        Guarda un usuario en el repositorio.
        
        Args:
            user (User): La entidad usuario a guardar
            
        Raises:
            UserAlreadyExistsError: Si ya existe un usuario con el mismo email
            RepositoryError: Si ocurre un error de persistencia
        """
        pass

    @abstractmethod
    async def find_by_id(self, user_id: UserId) -> Optional[User]:
        """
        Busca un usuario por su ID único.
        
        Args:
            user_id (UserId): El identificador único del usuario
            
        Returns:
            Optional[User]: El usuario encontrado o None si no existe
            
        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_by_email(self, email: Email) -> Optional[User]:
        """
        Busca un usuario por su dirección de email.
        
        Args:
            email (Email): La dirección de email del usuario
            
        Returns:
            Optional[User]: El usuario encontrado o None si no existe
            
        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def exists_by_email(self, email: Email) -> bool:
        """
        Verifica si existe un usuario con el email especificado.
        
        Args:
            email (Email): La dirección de email a verificar
            
        Returns:
            bool: True si existe, False si no existe
            
        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_by_full_name(self, full_name: str) -> Optional[User]:
        """
        Busca un usuario por su nombre completo (first_name + last_name).
        
        Args:
            full_name (str): El nombre completo del usuario
            
        Returns:
            Optional[User]: El usuario encontrado o None si no existe
            
        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def update(self, user: User) -> None:
        """
        Actualiza un usuario existente en el repositorio.
        
        Args:
            user (User): La entidad usuario con los datos actualizados
            
        Raises:
            UserNotFoundError: Si el usuario no existe
            RepositoryError: Si ocurre un error de persistencia
        """
        pass

    @abstractmethod
    async def delete_by_id(self, user_id: UserId) -> bool:
        """
        Elimina un usuario del repositorio por su ID.
        
        Args:
            user_id (UserId): El identificador único del usuario
            
        Returns:
            bool: True si se eliminó, False si no existía
            
        Raises:
            RepositoryError: Si ocurre un error de persistencia
        """
        pass

    @abstractmethod
    async def find_all(self, limit: int = 100, offset: int = 0) -> List[User]:
        """
        Obtiene una lista paginada de usuarios.
        
        Args:
            limit (int): Número máximo de usuarios a retornar (default: 100)
            offset (int): Número de usuarios a saltar (default: 0)
            
        Returns:
            List[User]: Lista de usuarios encontrados
            
        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def count_all(self) -> int:
        """
        Cuenta el total de usuarios en el repositorio.

        Returns:
            int: Número total de usuarios

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_by_verification_token(self, token: str) -> Optional[User]:
        """
        Busca un usuario por su token de verificación de email.

        Args:
            token (str): El token de verificación

        Returns:
            Optional[User]: El usuario encontrado o None si no existe

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass