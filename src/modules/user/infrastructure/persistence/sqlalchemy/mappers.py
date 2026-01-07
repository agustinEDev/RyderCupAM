# src/modules/user/infrastructure/persistence/sqlalchemy/mappers.py
import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table, inspect
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.orm import composite
from sqlalchemy.types import CHAR, TypeDecorator

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.handicap import Handicap
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_id import UserId

# Importar registry y metadata centralizados
from src.shared.infrastructure.persistence.sqlalchemy.base import mapper_registry, metadata

# Importar CountryCodeDecorator del shared domain
from src.shared.infrastructure.persistence.sqlalchemy.country_mappers import CountryCodeDecorator


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
    'users',
    metadata,
    Column('id', UserIdDecorator, primary_key=True),
    Column('first_name', String(50), nullable=False),
    Column('last_name', String(50), nullable=False),
    Column('email', String(255), nullable=False, unique=True),
    Column('password', String(255), nullable=False),
    Column('handicap', HandicapDecorator, nullable=True),
    Column('handicap_updated_at', DateTime, nullable=True),
    Column('created_at', DateTime, nullable=False),
    Column('updated_at', DateTime, nullable=False),
    Column('email_verified', Boolean, nullable=False, default=False),
    Column('verification_token', String(255), nullable=True),
    Column('password_reset_token', String(255), nullable=True),
    Column('reset_token_expires_at', DateTime, nullable=True),
    Column('country_code', CountryCodeDecorator, ForeignKey('countries.code', ondelete='SET NULL'), nullable=True),
    # Account Lockout fields (v1.13.0)
    Column('failed_login_attempts', Integer, nullable=False, default=0),
    Column('locked_until', DateTime, nullable=True),
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
        mapper_registry.map_imperatively(User, users_table, properties={
            # Mapeamos las columnas de los ValueObjects a atributos "privados"
            # para que SQLAlchemy no intente mapearlas automáticamente a los públicos.
            '_email': users_table.c.email,
            '_password': users_table.c.password,

            # Ahora, creamos los atributos públicos usando 'composite' y apuntando
            # a los atributos privados que acabamos de definir.
            'email': composite(Email, '_email'),
            'password': composite(Password, '_password'),
            # handicap se mapea directamente - el HandicapDecorator maneja la conversión y None
        })

    # Mapear RefreshToken entity (v1.8.0 - Session Timeout)
    from src.modules.user.infrastructure.persistence.sqlalchemy.refresh_token_mapper import (
        start_mappers as start_refresh_token_mappers
    )
    start_refresh_token_mappers()
