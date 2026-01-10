"""
User Unit of Work Interface - User Module Domain Layer

Define el contrato específico para el Unit of Work del módulo de usuarios.
Esta interfaz extiende la base añadiendo acceso al repositorio de usuarios.
"""

from abc import abstractmethod

from src.shared.domain.repositories.unit_of_work_interface import UnitOfWorkInterface

from ..repositories.password_history_repository_interface import (
    PasswordHistoryRepositoryInterface,
)
from ..repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)
from ..repositories.user_device_repository_interface import (
    UserDeviceRepositoryInterface,
)
from ..repositories.user_repository_interface import UserRepositoryInterface


class UserUnitOfWorkInterface(UnitOfWorkInterface):
    """
    Interfaz específica para el Unit of Work del módulo de usuarios.

    Proporciona acceso coordinated a todos los repositorios relacionados
    con el dominio de usuarios, manteniendo consistencia transaccional.

    Repositorios incluidos (v1.13.0):
    - users: UserRepositoryInterface
    - refresh_tokens: RefreshTokenRepositoryInterface (Session Timeout)
    - password_history: PasswordHistoryRepositoryInterface (Password History)
    - user_devices: UserDeviceRepositoryInterface (Device Fingerprinting)

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

    @property
    @abstractmethod
    def refresh_tokens(self) -> RefreshTokenRepositoryInterface:
        """
        Acceso al repositorio de refresh tokens dentro de la transacción.

        Proporciona una instancia del repositorio de refresh tokens que participa
        en la misma transacción que otros repositorios del Unit of Work.

        Session Timeout (v1.8.0):
        - Permite crear refresh tokens en login
        - Permite validar y revocar tokens en logout
        - Mantiene consistencia transaccional con users

        Returns:
            RefreshTokenRepositoryInterface: Repositorio de refresh tokens transaccional
        """
        pass

    @property
    @abstractmethod
    def password_history(self) -> PasswordHistoryRepositoryInterface:
        """
        Acceso al repositorio de historial de contraseñas dentro de la transacción.

        Proporciona una instancia del repositorio de password history que participa
        en la misma transacción que otros repositorios del Unit of Work.

        Password History (v1.13.0):
        - Permite guardar hashes de contraseñas al cambiar
        - Permite consultar últimas 5 contraseñas para validación
        - Mantiene consistencia transaccional con users

        Returns:
            PasswordHistoryRepositoryInterface: Repositorio de password history transaccional
        """
        pass

    @property
    @abstractmethod
    def user_devices(self) -> UserDeviceRepositoryInterface:
        """
        Acceso al repositorio de dispositivos de usuario dentro de la transacción.

        Proporciona una instancia del repositorio de user devices que participa
        en la misma transacción que otros repositorios del Unit of Work.

        Device Fingerprinting (v1.13.0):
        - Permite registrar/actualizar dispositivos en login/refresh
        - Permite listar dispositivos activos del usuario
        - Permite revocar dispositivos sospechosos
        - Mantiene consistencia transaccional con users

        Returns:
            UserDeviceRepositoryInterface: Repositorio de user devices transaccional
        """
        pass
