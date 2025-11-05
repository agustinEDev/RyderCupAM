# src/modules/user/domain/services/user_finder.py

from typing import Optional
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.email import Email

class UserFinder:
    """
    Servicio de Dominio para encontrar usuarios.
    Encapsula la lógica de búsqueda y la hace reutilizable.
    """
    def __init__(self, user_repository: UserRepositoryInterface):
        self._user_repository = user_repository

    async def by_email(self, email: Email) -> Optional[User]:
        """Encuentra un usuario por su correo electrónico."""
        return await self._user_repository.find_by_email(email)

    # En el futuro, podríamos añadir más métodos:
    # async def by_id(self, user_id: UserId) -> Optional[User]: ...
    # async def active_users(self) -> List[User]: ...