"""
User Repository Interface - Domain Layer

Define el contrato para la persistencia de usuarios siguiendo principios de Clean Architecture.
Esta interfaz pertenece al dominio y será implementada en la capa de infraestructura.
"""

from abc import ABC, abstractmethod

from ..entities.user import User
from ..value_objects.email import Email
from ..value_objects.user_id import UserId


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
    async def find_by_id(self, user_id: UserId) -> User | None:
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
    async def find_by_id_for_update(self, user_id: UserId) -> User | None:
        """
        Busca un usuario por su ID con bloqueo de fila (SELECT ... FOR UPDATE).

        Usar dentro de una transacción cuando la operación es read-modify-write
        y debe serializarse frente a otras transacciones concurrentes sobre el
        mismo usuario (p.ej. podar el historial de avatares subidos).

        Args:
            user_id (UserId): El identificador único del usuario

        Returns:
            Optional[User]: El usuario encontrado (con la fila bloqueada) o None

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_by_ids(self, user_ids: list[UserId]) -> list[User]:
        """
        Busca múltiples usuarios por sus IDs en una sola consulta.

        Args:
            user_ids (list[UserId]): Lista de identificadores únicos

        Returns:
            list[User]: Lista de usuarios encontrados (puede ser menor que user_ids si algunos no existen)
        """
        pass

    @abstractmethod
    async def find_by_email(self, email: Email) -> User | None:
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
    async def find_by_alias(self, alias: str) -> User | None:
        """
        Busca un usuario por su alias, ignorando mayúsculas.

        Es la consulta con la que se comprueba si un alias está libre antes de
        guardarlo. No sustituye al índice único de la base de datos: entre esta
        consulta y el commit cabe otra petición pidiendo el mismo alias.

        Args:
            alias (str): El alias a buscar

        Returns:
            Optional[User]: El usuario que lo tiene, o None si está libre

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_by_full_name(self, full_name: str) -> User | None:
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
    async def search_by_partial_name(self, query: str, limit: int = 10) -> list[User]:
        """
        Searches users whose first_name or last_name partially matches the query (case-insensitive).

        Solo devuelve cuentas activas: esta búsqueda está abierta a cualquier
        usuario registrado, así que una cuenta desactivada no puede aparecer en
        ella. Para ver también las desactivadas está el listado de
        administración, que filtra por `is_active` explícitamente.

        Args:
            query (str): Partial name to search for (min 2 characters)
            limit (int): Maximum number of results to return (default: 10)

        Returns:
            list[User]: List of matching active users
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
    async def find_all(
        self,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
        is_admin: bool | None = None,
        is_active: bool | None = None,
        email_verified: bool | None = None,
    ) -> list[User]:
        """
        Obtiene una lista paginada de usuarios, opcionalmente filtrada.

        Args:
            limit (int): Número máximo de usuarios a retornar (default: 100)
            offset (int): Número de usuarios a saltar (default: 0)
            search (str | None): Si se indica, filtra por coincidencia parcial
                (case-insensitive) en nombre, apellidos o email
            is_admin (bool | None): Si se indica, filtra por rol (admin/jugador)
            is_active (bool | None): Si se indica, filtra por cuentas activas/desactivadas
            email_verified (bool | None): Si se indica, filtra por email verificado o no

        Returns:
            List[User]: Lista de usuarios encontrados

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def count_all(
        self,
        search: str | None = None,
        is_admin: bool | None = None,
        is_active: bool | None = None,
        email_verified: bool | None = None,
    ) -> int:
        """
        Cuenta usuarios, opcionalmente filtrados (ver find_all).

        Returns:
            int: Número total de usuarios que coinciden con el filtro

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_by_verification_token(self, token: str) -> User | None:
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

    @abstractmethod
    async def find_by_password_reset_token(self, token: str) -> User | None:
        """
        Busca un usuario por su token de reseteo de contraseña.

        Args:
            token (str): El token de reseteo de contraseña (generado con generate_password_reset_token)

        Returns:
            Optional[User]: El usuario encontrado o None si no existe o el token expiró

        Raises:
            RepositoryError: Si ocurre un error de consulta

        Security:
            - Solo busca tokens activos (no nulos)
            - NO valida expiración (esa lógica está en User.can_reset_password())
            - Usa índice único ix_users_password_reset_token para búsqueda rápida

        Example:
            >>> user = await repository.find_by_password_reset_token("abc123...")
            >>> if user and user.can_reset_password("abc123..."):
            ...     # Token válido y no expirado
        """
        pass
