"""
SQLAlchemy Mapper para ProfilePhoto (modulo Social).

Tabla:
- profile_photos
"""

import uuid
from typing import Any

import sqlalchemy.types
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Table,
    inspect,
)
from sqlalchemy.dialects import postgresql

from src.modules.social.domain.entities.profile_photo import ProfilePhoto
from src.modules.social.domain.value_objects.profile_photo_id import ProfilePhotoId
from src.modules.social.infrastructure.persistence.mappers.friendship_mapper import (
    SocialUserIdType,
)
from src.shared.infrastructure.persistence.sqlalchemy.base import mapper_registry, metadata


class ProfilePhotoIdType(sqlalchemy.types.TypeDecorator[ProfilePhotoId]):
    """TypeDecorator para ProfilePhotoId."""

    impl = postgresql.UUID(as_uuid=True)
    cache_ok = True

    def process_bind_param(self, value: ProfilePhotoId | None, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        return value.value

    def process_result_value(self, value: Any, dialect: Any) -> ProfilePhotoId | None:
        if value is None:
            return None
        return ProfilePhotoId(value)


profile_photos_table = Table(
    "profile_photos",
    metadata,
    Column("id", ProfilePhotoIdType, primary_key=True, default=uuid.uuid4),
    Column(
        "user_id",
        SocialUserIdType,
        # Al borrar la cuenta desaparecen sus fotos: no deben sobrevivir a su dueño
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # Los bytes de la imagen ya procesada. Postgres guarda los BYTEA grandes
    # comprimidos en una tabla auxiliar (TOAST), asi que su peso no penaliza a
    # ninguna consulta que no pida esta columna — que es justo lo que hace el
    # listado de la galeria
    Column("image_data", LargeBinary, nullable=False),
    Column("content_type", String(50), nullable=False),
    Column("caption", String(280), nullable=True),
    Column("created_at", DateTime, nullable=False),
    # La galeria siempre se pide igual: las fotos de este jugador, de la mas
    # reciente a la mas antigua
    Index("ix_profile_photos_user_created", "user_id", "created_at"),
)


def start_profile_photo_mappers() -> None:
    """
    Inicia el mapeo de ProfilePhoto. Idempotente de verdad.

    Se pregunta con `inspect(..., raiseerr=False)` y no con
    `ProfilePhoto not in mapper_registry.mappers`: ese conjunto contiene objetos
    `Mapper`, no clases, asi que la pregunta siempre da cierto y la segunda
    llamada revienta (ver BE #179).
    """
    if inspect(ProfilePhoto, raiseerr=False) is None:
        mapper_registry.map_imperatively(
            ProfilePhoto,
            profile_photos_table,
            properties={
                "_id": profile_photos_table.c.id,
                "_user_id": profile_photos_table.c.user_id,
                "_image_data": profile_photos_table.c.image_data,
                "_content_type": profile_photos_table.c.content_type,
                "_caption": profile_photos_table.c.caption,
                "_created_at": profile_photos_table.c.created_at,
            },
        )
