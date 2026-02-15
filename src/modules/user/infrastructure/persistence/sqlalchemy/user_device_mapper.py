# src/modules/user/infrastructure/persistence/sqlalchemy/user_device_mapper.py
"""
User Device Mapper - Infrastructure Layer

Mapeo imperativo entre la entidad UserDevice y la tabla user_devices.
"""

import contextlib
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, Text, event
from sqlalchemy.types import CHAR, TypeDecorator

from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.persistence.sqlalchemy.base import (
    mapper_registry,
    metadata,
)

# --- TypeDecorators ---


class UserDeviceIdDecorator(TypeDecorator):
    """TypeDecorator para UserDeviceId → CHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, UserDeviceId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return UserDeviceId(uuid.UUID(value))


class UserIdDecorator(TypeDecorator):
    """TypeDecorator para UserId → CHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, UserId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return UserId(uuid.UUID(value))


# --- Tabla ---

user_devices_table = Table(
    "user_devices",
    metadata,
    Column("id", UserDeviceIdDecorator, primary_key=True),
    Column(
        "user_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("device_name", String(200), nullable=False),
    Column("user_agent", Text, nullable=False),
    Column("ip_address", String(45), nullable=False),
    Column("fingerprint_hash", String(64), nullable=False),
    Column("is_active", Boolean, nullable=False, server_default="true"),
    Column("last_used_at", DateTime, nullable=False),
    Column("created_at", DateTime, nullable=False),
)


# --- Mapper ---


def start_user_device_mappers():
    """Inicia el mapper imperativo de UserDevice → user_devices."""
    with contextlib.suppress(Exception):
        # Ya mapeado, ignorar (puede suceder en pytest con xdist)
        mapper_registry.map_imperatively(
            UserDevice,
            user_devices_table,
            properties={
                "_id": user_devices_table.c.id,
                "_user_id": user_devices_table.c.user_id,
                # Fingerprint se almacena como columnas individuales
                # y se reconstruye en el repository usando reconstitute()
                "_device_name": user_devices_table.c.device_name,
                "_user_agent": user_devices_table.c.user_agent,
                "_ip_address": user_devices_table.c.ip_address,
                "_fingerprint_hash": user_devices_table.c.fingerprint_hash,
                "_is_active": user_devices_table.c.is_active,
                "_last_used_at": user_devices_table.c.last_used_at,
                "_created_at": user_devices_table.c.created_at,
            },
        )

    # Event listener: initialize _domain_events when SQLAlchemy loads from DB
    # (replaces @reconstructor that was previously in the domain entity)
    @event.listens_for(UserDevice, "load")
    def _init_user_device_domain_events(target, _context):
        if not hasattr(target, "_domain_events"):
            target._domain_events = []
