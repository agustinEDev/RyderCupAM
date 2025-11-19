# src/modules/user/infrastructure/persistence/sqlalchemy/mappers.py
import uuid
from sqlalchemy import (
    Table, Column, String, DateTime, Float, Boolean
)
from sqlalchemy.orm import composite
from sqlalchemy.types import TypeDecorator, CHAR
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password

# Importar registry y metadata centralizados
from src.shared.infrastructure.persistence.sqlalchemy.base import (
    mapper_registry,
    metadata
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
    Column('handicap', Float, nullable=True),
    Column('handicap_updated_at', DateTime, nullable=True),
    Column('created_at', DateTime, nullable=False),
    Column('updated_at', DateTime, nullable=False),
    Column('email_verified', Boolean, nullable=False, default=False),
    Column('verification_token', String(255), nullable=True),
)

def start_mappers():
    """
    Inicia el mapeo entre las entidades de dominio y las tablas de la base de datos.
    Es idempotente, por lo que se puede llamar de forma segura varias veces.
    """
    # La forma correcta de comprobar si un mapper ya existe para una clase
    if User not in mapper_registry.mappers:
        mapper_registry.map_imperatively(User, users_table, properties={
            # Mapeamos las columnas de los ValueObjects a atributos "privados"
            # para que SQLAlchemy no intente mapearlas automáticamente a los públicos.
            '_email': users_table.c.email,
            '_password': users_table.c.password,

            # Ahora, creamos los atributos públicos usando 'composite' y apuntando
            # a los atributos privados que acabamos de definir.
            'email': composite(Email, '_email'),
            'password': composite(Password, '_password'),
        })