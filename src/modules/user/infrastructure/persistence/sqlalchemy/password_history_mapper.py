# src/modules/user/infrastructure/persistence/sqlalchemy/password_history_mapper.py
"""
Password History Mapper - Infrastructure Layer

Mapeo imperativo entre la entidad PasswordHistory y la tabla password_history.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, inspect
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.types import CHAR, TypeDecorator

from src.modules.user.domain.entities.password_history import PasswordHistory
from src.modules.user.domain.value_objects.password_history_id import PasswordHistoryId
from src.modules.user.domain.value_objects.user_id import UserId

# Importar registry y metadata centralizados
from src.shared.infrastructure.persistence.sqlalchemy.base import mapper_registry, metadata


# --- TypeDecorator para PasswordHistoryId ---
class PasswordHistoryIdDecorator(TypeDecorator):
    """TypeDecorator para manejar PasswordHistoryId como CHAR(36) en BD."""
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(
        self,
        value: PasswordHistoryId | str,
        dialect
    ) -> str | None:
        """Convierte PasswordHistoryId o string a string para BD."""
        if isinstance(value, PasswordHistoryId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str, dialect) -> PasswordHistoryId | None:
        """Convierte el string de BD de vuelta a PasswordHistoryId."""
        if value is None:
            return None
        return PasswordHistoryId(uuid.UUID(value))


# --- TypeDecorator para UserId (reutilizado) ---
class UserIdDecorator(TypeDecorator):
    """TypeDecorator para manejar UserId como CHAR(36) en BD."""
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: UserId | str, dialect) -> str | None:
        """Convierte UserId o string a string para BD."""
        if isinstance(value, UserId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str, dialect) -> UserId | None:
        """Convierte el string de BD de vuelta a UserId."""
        if value is None:
            return None
        return UserId(uuid.UUID(value))


# --- Definición de la Tabla ---
password_history_table = Table(
    'password_history',
    metadata,
    Column('id', PasswordHistoryIdDecorator, primary_key=True),
    Column('user_id', UserIdDecorator, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    Column('password_hash', String(255), nullable=False),
    Column('created_at', DateTime, nullable=False),
)


def start_mappers():
    """
    Inicia el mapeo entre PasswordHistory y password_history table.
    Es idempotente, por lo que se puede llamar de forma segura varias veces.
    """
    # Verificar si PasswordHistory ya está mapeado (idempotencia)
    try:
        inspect(PasswordHistory)
        # Si llegamos aquí, PasswordHistory ya está mapeado
    except NoInspectionAvailable:
        # PasswordHistory no está mapeado, proceder a mapear
        mapper_registry.map_imperatively(
            PasswordHistory,
            password_history_table,
            properties={
                # Mapeo directo de columnas a atributos
                # Los Value Objects (PasswordHistoryId, UserId) se manejan con TypeDecorators
            }
        )
