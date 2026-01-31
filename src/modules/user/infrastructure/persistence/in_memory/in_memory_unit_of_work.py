from src.modules.user.domain.repositories.password_history_repository_interface import (
    PasswordHistoryRepositoryInterface,
)
from src.modules.user.domain.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)
from src.modules.user.domain.repositories.user_device_repository_interface import (
    UserDeviceRepositoryInterface,
)
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.infrastructure.persistence.in_memory.in_memory_password_history_repository import (
    InMemoryPasswordHistoryRepository,
)
from src.modules.user.infrastructure.persistence.in_memory.in_memory_refresh_token_repository import (
    InMemoryRefreshTokenRepository,
)
from src.modules.user.infrastructure.persistence.in_memory.in_memory_user_device_repository import (
    InMemoryUserDeviceRepository,
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
        self._password_history = InMemoryPasswordHistoryRepository()
        self._user_devices = InMemoryUserDeviceRepository()
        self.committed = False

    @property
    def users(self) -> UserRepositoryInterface:
        """Propiedad para acceder al repositorio de usuarios."""
        return self._users

    @property
    def refresh_tokens(self) -> RefreshTokenRepositoryInterface:
        """Propiedad para acceder al repositorio de refresh tokens."""
        return self._refresh_tokens

    @property
    def password_history(self) -> PasswordHistoryRepositoryInterface:
        """Propiedad para acceder al repositorio de password history."""
        return self._password_history

    @property
    def user_devices(self) -> UserDeviceRepositoryInterface:
        """Propiedad para acceder al repositorio de user devices."""
        return self._user_devices

    async def __aenter__(self):
        self.committed = False
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Finaliza el contexto async - maneja commit/rollback automáticamente.

        Comportamiento:
        - Si NO hubo excepción → commit() automático
        - Si hubo excepción → rollback() automático

        Args:
            exc_type: Tipo de excepción (None si no hubo error)
            exc_val: Valor de la excepción
            exc_tb: Traceback de la excepción
        """
        if exc_type:
            # Si hubo excepción, hacer rollback
            await self.rollback()
        else:
            # Si todo fue exitoso, hacer commit automáticamente
            try:
                await self.commit()
            except Exception:
                # Si commit falla, hacer rollback
                await self.rollback()
                raise

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
