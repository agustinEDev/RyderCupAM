from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import AliasAlreadyTakenError
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
        self._users: dict[UserId, User] = {}

    async def save(self, user: User) -> None:
        self._guard_alias_is_free(user)
        self._users[user.id] = user

    async def find_by_id(self, user_id: UserId) -> User | None:
        return self._users.get(user_id)

    async def find_by_id_for_update(self, user_id: UserId) -> User | None:
        # En memoria no hay concurrencia real de transacciones que bloquear.
        return self._users.get(user_id)

    async def find_by_ids(self, user_ids: list[UserId]) -> list[User]:
        return [self._users[uid] for uid in user_ids if uid in self._users]

    async def find_by_email(self, email: Email) -> User | None:
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    async def find_by_alias(self, alias: str) -> User | None:
        normalized = alias.strip().lower()
        if not normalized:
            return None
        for user in self._users.values():
            if user.alias and user.alias.lower() == normalized:
                return user
        return None

    def _guard_alias_is_free(self, user: User) -> None:
        """
        Impone la misma unicidad que el índice de la base de datos.

        Sin esto, un caso de uso podría guardar dos veces el mismo alias en los
        tests unitarios y pasar, contradiciendo lo que hace el repositorio real
        en producción.
        """
        if not user.alias:
            return
        alias_lower = user.alias.lower()
        for other in self._users.values():
            if other.id != user.id and other.alias and other.alias.lower() == alias_lower:
                raise AliasAlreadyTakenError(f"El alias '{user.alias}' ya está en uso.")

    def _matches_search(self, user: User, search: str | None) -> bool:
        if not search or not search.strip():
            return True
        q = search.strip().lower()
        full_name = f"{user.first_name} {user.last_name}".lower()
        email = str(user.email).lower() if user.email else ""
        alias = user.alias.lower() if user.alias else ""
        return (
            q in user.first_name.lower()
            or q in user.last_name.lower()
            or q in full_name
            or q in email
            or (bool(alias) and q in alias)
        )

    def _matches_filters(
        self,
        user: User,
        search: str | None,
        is_admin: bool | None,
        is_active: bool | None,
        email_verified: bool | None,
    ) -> bool:
        if not self._matches_search(user, search):
            return False
        if is_admin is not None and user.is_admin != is_admin:
            return False
        if is_active is not None and user.is_active != is_active:
            return False
        return email_verified is None or user.email_verified == email_verified

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
            limit: Número máximo de usuarios a retornar
            offset: Número de usuarios a saltar
            search: Filtro opcional por nombre/apellidos/email
            is_admin: Filtro opcional por rol
            is_active: Filtro opcional por cuentas activas/desactivadas
            email_verified: Filtro opcional por verificación de email

        Returns:
            Lista de usuarios paginada
        """
        matching = [
            u
            for u in self._users.values()
            if self._matches_filters(u, search, is_admin, is_active, email_verified)
        ]
        matching.sort(key=lambda u: (u.created_at, str(u.id)), reverse=True)
        return matching[offset : offset + limit]

    async def delete_by_id(self, user_id: UserId) -> bool:
        if user_id in self._users:
            del self._users[user_id]
            return True
        return False

    async def update(self, user: User) -> None:
        if user.id in self._users:
            self._guard_alias_is_free(user)
            self._users[user.id] = user

    async def find_by_full_name(self, full_name: str) -> User | None:
        full_name_lower = full_name.lower().strip()
        for user in self._users.values():
            user_full_name = f"{user.first_name} {user.last_name}".lower()
            if user_full_name == full_name_lower:
                return user
        return None

    MIN_SEARCH_LENGTH = 2

    async def search_by_partial_name(self, query: str, limit: int = 10) -> list[User]:
        """
        Searches active users by partial name or alias match.

        Requires at least 2 characters. Excluye las cuentas desactivadas, igual
        que el repositorio real, y busca en el alias por la misma razon.
        """
        query_lower = query.lower().strip()
        if len(query_lower) < self.MIN_SEARCH_LENGTH:
            return []
        results = []
        for user in self._users.values():
            if not user.is_active:
                continue
            full_name = f"{user.first_name} {user.last_name}".lower()
            alias = user.alias.lower() if user.alias else ""
            if (
                query_lower in full_name
                or query_lower in user.first_name.lower()
                or query_lower in user.last_name.lower()
                or (bool(alias) and query_lower in alias)
            ):
                results.append(user)
                if len(results) >= limit:
                    break
        return results

    async def exists_by_email(self, email: Email) -> bool:
        return any(user.email == email for user in self._users.values())

    async def count_all(
        self,
        search: str | None = None,
        is_admin: bool | None = None,
        is_active: bool | None = None,
        email_verified: bool | None = None,
    ) -> int:
        return len(
            [
                u
                for u in self._users.values()
                if self._matches_filters(u, search, is_admin, is_active, email_verified)
            ]
        )

    async def find_by_verification_token(self, token: str) -> User | None:
        """Busca un usuario por su token de verificación."""
        for user in self._users.values():
            if user.verification_token == token:
                return user
        return None

    async def find_by_password_reset_token(self, token: str) -> User | None:
        """Busca un usuario por su token de reseteo de contraseña."""
        for user in self._users.values():
            if user.password_reset_token == token:
                return user
        return None
