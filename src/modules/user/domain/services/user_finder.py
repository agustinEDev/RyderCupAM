# src/modules/user/domain/services/user_finder.py


from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.user_id import UserId


class UserFinder:
    """
    Servicio de Dominio para encontrar usuarios.
    Encapsula la lógica de búsqueda y la hace reutilizable.
    """
    def __init__(self, user_repository: UserRepositoryInterface):
        self._user_repository = user_repository

    async def by_email(self, email: Email) -> User | None:
        """Encuentra un usuario por su correo electrónico."""
        return await self._user_repository.find_by_email(email)

    async def by_id(self, user_id: UserId) -> User | None:
        """Encuentra un usuario por su ID."""
        return await self._user_repository.find_by_id(user_id)

    async def by_full_name(self, full_name: str) -> User | None:
        """Encuentra un usuario por su nombre completo."""
        return await self._user_repository.find_by_full_name(full_name)

    async def by_verification_token(self, token: str) -> User | None:
        """Encuentra un usuario por su token de verificación."""
        return await self._user_repository.find_by_verification_token(token)
