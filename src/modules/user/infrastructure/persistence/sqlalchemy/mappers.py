# src/modules/user/infrastructure/persistence/sqlalchemy/mappers.py
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    inspect,
)
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.orm import composite
from sqlalchemy.types import CHAR, TypeDecorator

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.handicap import Handicap
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender

# Importar registry y metadata centralizados
from src.shared.infrastructure.persistence.sqlalchemy.base import (
    mapper_registry,
    metadata,
)

# Importar CountryCodeDecorator del shared domain
from src.shared.infrastructure.persistence.sqlalchemy.country_mappers import (
    CountryCodeDecorator,
)


# --- TypeDecorator para UserId ---
# Le enseña a SQLAlchemy a manejar nuestro ValueObject UserId.
class UserIdDecorator(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: UserId | str, dialect) -> str | None:
        """Convierte el objeto UserId o un string a un string para guardarlo en la BD."""
        if isinstance(value, UserId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str, dialect) -> UserId | None:
        """Convierte el string de la BD de vuelta a un objeto UserId."""
        if value is None:
            return None
        return UserId(uuid.UUID(value))


# --- TypeDecorator para Gender ---
class GenderDecorator(TypeDecorator):
    """Convierte entre Gender enum y string en BD."""

    impl = String(10)
    cache_ok = True

    def process_bind_param(self, value: Gender | None, dialect) -> str | None:
        if value is None:
            return None
        return value.value

    def process_result_value(self, value: str | None, dialect) -> Gender | None:
        if value is None:
            return None
        return Gender(value)


# --- TypeDecorator para Handicap ---
# Le enseña a SQLAlchemy a manejar nuestro ValueObject Handicap.
class HandicapDecorator(TypeDecorator):
    impl = Float
    cache_ok = True

    def process_bind_param(self, value, dialect) -> float | None:
        """Convierte el objeto Handicap a float para guardarlo en la BD."""

        if isinstance(value, Handicap):
            return value.value
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def process_result_value(self, value: float, dialect):
        """Convierte el float de la BD de vuelta a un objeto Handicap."""

        if value is None:
            return None
        return Handicap(value)


# --- Registro y Metadatos ---
# (Importados de base.py - ver imports arriba)

# --- Definición de la Tabla ---
users_table = Table(
    "users",
    metadata,
    Column("id", UserIdDecorator, primary_key=True),
    Column("first_name", String(50), nullable=False),
    Column("last_name", String(50), nullable=False),
    Column("email", String(255), nullable=False, unique=True),
    Column("password", String(255), nullable=True),  # Nullable for OAuth-only users
    Column("handicap", HandicapDecorator, nullable=True),
    Column("handicap_updated_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    Column("email_verified", Boolean, nullable=False, default=False),
    Column("verification_token", String(255), nullable=True),
    Column("password_reset_token", String(255), nullable=True),
    Column("reset_token_expires_at", DateTime, nullable=True),
    Column(
        "country_code",
        CountryCodeDecorator,
        ForeignKey("countries.code", ondelete="SET NULL"),
        nullable=True,
    ),
    # Account Lockout fields (v1.13.0)
    Column("failed_login_attempts", Integer, nullable=False, default=0),
    Column("locked_until", DateTime, nullable=True),
    # RBAC field (v2.0.0)
    Column("is_admin", Boolean, nullable=False, default=False),
    # Gender field (tee system refactor)
    Column("gender", GenderDecorator(), nullable=True),
)


def start_mappers():
    """
    Inicia el mapeo entre las entidades de dominio y las tablas de la base de datos.
    Es idempotente, por lo que se puede llamar de forma segura varias veces.
    """
    # Verificar si User ya está mapeado usando inspect() (idempotencia)
    try:
        inspect(User)
        # Si llegamos aquí, User ya está mapeado
    except NoInspectionAvailable:
        # User no está mapeado, proceder a mapear
        mapper_registry.map_imperatively(
            User,
            users_table,
            properties={
                # Scalar fields → private attrs (encapsulación, issue #109)
                "_id": users_table.c.id,
                "_first_name": users_table.c.first_name,
                "_last_name": users_table.c.last_name,
                "_handicap": users_table.c.handicap,
                "_handicap_updated_at": users_table.c.handicap_updated_at,
                "_created_at": users_table.c.created_at,
                "_updated_at": users_table.c.updated_at,
                "_email_verified": users_table.c.email_verified,
                "_verification_token": users_table.c.verification_token,
                "_country_code": users_table.c.country_code,
                "_password_reset_token": users_table.c.password_reset_token,
                "_reset_token_expires_at": users_table.c.reset_token_expires_at,
                "_failed_login_attempts": users_table.c.failed_login_attempts,
                "_locked_until": users_table.c.locked_until,
                "_is_admin": users_table.c.is_admin,
                "_gender": users_table.c.gender,
                # Value Objects de una columna (Email, Password) → mapeamos la columna
                # cruda a un atributo "_value" y componemos el VO real sobre el
                # atributo privado "_email"/"_password" que respalda la @property
                # pública de solo lectura del dominio.
                "_email_value": users_table.c.email,
                "_password_value": users_table.c.password,
                "_email": composite(Email, "_email_value"),
                "_password": composite(Password, "_password_value"),
            },
        )

    # Mapear RefreshToken, PasswordHistory y UserDevice entities
    # Imports dinámicos necesarios para evitar circular imports
    from src.modules.user.infrastructure.persistence.sqlalchemy.password_history_mapper import (  # noqa: PLC0415
        start_mappers as start_password_history_mappers,
    )
    from src.modules.user.infrastructure.persistence.sqlalchemy.refresh_token_mapper import (  # noqa: PLC0415
        start_mappers as start_refresh_token_mappers,
    )
    from src.modules.user.infrastructure.persistence.sqlalchemy.user_device_mapper import (  # noqa: PLC0415
        start_user_device_mappers,
    )
    from src.modules.user.infrastructure.persistence.sqlalchemy.user_oauth_account_mapper import (  # noqa: PLC0415
        start_oauth_account_mappers,
    )

    start_refresh_token_mappers()
    start_password_history_mappers()
    start_user_device_mappers()
    start_oauth_account_mappers()
