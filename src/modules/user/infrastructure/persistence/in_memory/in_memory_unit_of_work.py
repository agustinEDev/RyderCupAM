from src.modules.user.domain.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.infrastructure.persistence.in_memory.in_memory_refresh_token_repository import (
    InMemoryRefreshTokenRepository,
)
from src.modules.user.infrastructure.persistence.in_memory.in_memory_user_repository import (
    InMemoryUserRepository,
)


class InMemoryUnitOfWork(UserUnitOfWorkInterface):
    """
    Implementación en memoria de la Unit of Work para testing.
    """

    def __init__(self):
        self._users = InMemoryUserRepository()
        self._refresh_tokens = InMemoryRefreshTokenRepository()
        self.committed = False

    @property
    def users(self) -> UserRepositoryInterface:
        """Propiedad para acceder al repositorio de usuarios."""
        return self._users

    @property
    def refresh_tokens(self) -> RefreshTokenRepositoryInterface:
        """Propiedad para acceder al repositorio de refresh tokens."""
        return self._refresh_tokens

    async def __aenter__(self):
        self.committed = False
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.committed = False

    async def flush(self) -> None:
        """En memoria, flush no tiene un efecto real."""
        pass

    def is_active(self) -> bool:
        """En memoria, la transacción siempre se considera activa."""
        return True
