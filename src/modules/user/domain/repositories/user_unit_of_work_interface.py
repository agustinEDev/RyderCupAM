"""
User Unit of Work Interface - User Module Domain Layer

Define el contrato específico para el Unit of Work del módulo de usuarios.
Esta interfaz extiende la base añadiendo acceso al repositorio de usuarios.
"""

from abc import abstractmethod
from ..repositories.user_repository_interface import UserRepositoryInterface
from src.shared.domain.repositories.unit_of_work_interface import UnitOfWorkInterface


class UserUnitOfWorkInterface(UnitOfWorkInterface):
    """
    Interfaz específica para el Unit of Work del módulo de usuarios.
    
    Proporciona acceso coordinated a todos los repositorios relacionados
    con el dominio de usuarios, manteniendo consistencia transaccional.
    
    Uso típico en casos de uso:
    ```python
    async def register_user(self, command: RegisterUserCommand) -> UserResponse:
        async with self._uow:
            # Verificar que el email no existe
            if await self._uow.users.exists_by_email(command.email):
                raise UserAlreadyExistsError("Email already registered")
            
            # Crear y guardar usuario
            user = User.create(...)
            await self._uow.users.save(user)
            
            # Commit automático al salir del contexto
        
        return UserResponse.from_user(user)
    ```
    """
    
    @property
    @abstractmethod
    def users(self) -> UserRepositoryInterface:
        """
        Acceso al repositorio de usuarios dentro de la transacción.
        
        Proporciona una instancia del repositorio de usuarios que participa
        en la misma transacción que otros repositorios del Unit of Work.
        
        Returns:
            UserRepositoryInterface: Repositorio de usuarios transaccional
        """
        pass