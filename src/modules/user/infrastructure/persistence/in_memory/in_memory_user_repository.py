from typing import Dict, List, Optional

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryUserRepository(UserRepositoryInterface):
    """
    Implementación en memoria del repositorio de usuarios para testing.
    """

    def __init__(self):
        self._users: Dict[UserId, User] = {}

    async def save(self, user: User) -> None:
        self._users[user.id] = user

    async def find_by_id(self, user_id: UserId) -> Optional[User]:
        return self._users.get(user_id)

    async def find_by_email(self, email: Email) -> Optional[User]:
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    async def find_all(self) -> List[User]:
        return list(self._users.values())

    async def delete_by_id(self, user_id: UserId) -> None:
        if user_id in self._users:
            del self._users[user_id]

    async def update(self, user: User) -> None:
        if user.id in self._users:
            self._users[user.id] = user

    async def find_by_full_name(self, full_name: str) -> Optional[User]:
        full_name_lower = full_name.lower().strip()
        for user in self._users.values():
            user_full_name = f"{user.first_name} {user.last_name}".lower()
            if user_full_name == full_name_lower:
                return user
        return None

    async def exists_by_email(self, email: Email) -> bool:
        return any(user.email == email for user in self._users.values())

    async def count_all(self) -> int:
        return len(self._users)

    async def find_by_verification_token(self, token: str) -> Optional[User]:
        """Busca un usuario por su token de verificación."""
        for user in self._users.values():
            if user.verification_token == token:
                return user
        return None
