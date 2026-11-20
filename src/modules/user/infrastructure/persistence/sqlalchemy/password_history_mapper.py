# src/modules/user/infrastructure/persistence/sqlalchemy/password_history_mapper.py
"""
Password History Mapper - Infrastructure Layer

Mapeo imperativo entre la entidad PasswordHistory y la tabla password_history.
"""

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, inspect
from sqlalchemy.exc import NoInspectionAvailable

from src.modules.user.domain.entities.password_history import PasswordHistory
from src.modules.user.domain.value_objects.password_history_id import PasswordHistoryId
from src.modules.user.domain.value_objects.user_id import UserId

# Importar registry y metadata centralizados
from src.shared.infrastructure.persistence.sqlalchemy.base import (
    mapper_registry,
    metadata,
)
from src.shared.infrastructure.persistence.sqlalchemy.tipos_de_id import tipo_de_id

# --- TypeDecorator para PasswordHistoryId ---
PasswordHistoryIdDecorator = tipo_de_id(PasswordHistoryId)


# --- TypeDecorator para UserId (el de este mapper) ---
UserIdDecorator = tipo_de_id(UserId)


# --- Definición de la Tabla ---
password_history_table = Table(
    "password_history",
    metadata,
    Column("id", PasswordHistoryIdDecorator, primary_key=True),
    Column(
        "user_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("password_hash", String(255), nullable=False),
    Column("created_at", DateTime, nullable=False),
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
                # Mapeo directo de columnas a atributos privados (encapsulación,
                # issue #109). Los Value Objects (PasswordHistoryId, UserId) se
                # manejan con TypeDecorators, por lo que no requieren composite().
                "_id": password_history_table.c.id,
                "_user_id": password_history_table.c.user_id,
                "_password_hash": password_history_table.c.password_hash,
                "_created_at": password_history_table.c.created_at,
            },
        )
