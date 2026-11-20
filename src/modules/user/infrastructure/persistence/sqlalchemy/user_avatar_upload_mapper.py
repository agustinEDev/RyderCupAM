# src/modules/user/infrastructure/persistence/sqlalchemy/user_avatar_upload_mapper.py
"""
User Avatar Upload Mapper - Infrastructure Layer

Mapeo imperativo entre la entidad UserAvatarUpload y la tabla user_avatar_uploads.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, LargeBinary, String, Table, inspect
from sqlalchemy.exc import NoInspectionAvailable

from src.modules.user.domain.entities.user_avatar_upload import UserAvatarUpload
from src.modules.user.domain.value_objects.user_avatar_upload_id import UserAvatarUploadId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.persistence.sqlalchemy.base import (
    mapper_registry,
    metadata,
)
from src.shared.infrastructure.persistence.sqlalchemy.tipos_de_id import tipo_de_id

UserAvatarUploadIdDecorator = tipo_de_id(UserAvatarUploadId)
_AvatarUploadUserIdDecorator = tipo_de_id(UserId)


user_avatar_uploads_table = Table(
    "user_avatar_uploads",
    metadata,
    Column("id", UserAvatarUploadIdDecorator, primary_key=True),
    Column(
        "user_id",
        _AvatarUploadUserIdDecorator,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("image_data", LargeBinary, nullable=False),
    Column("content_type", String(50), nullable=False),
    Column("created_at", DateTime, nullable=False),
    Index("ix_user_avatar_uploads_user_created", "user_id", "created_at"),
)


def start_mappers():
    """
    Inicia el mapeo entre UserAvatarUpload y user_avatar_uploads table.
    Es idempotente, por lo que se puede llamar de forma segura varias veces.
    """
    try:
        inspect(UserAvatarUpload)
    except NoInspectionAvailable:
        mapper_registry.map_imperatively(
            UserAvatarUpload,
            user_avatar_uploads_table,
            properties={
                "_id": user_avatar_uploads_table.c.id,
                "_user_id": user_avatar_uploads_table.c.user_id,
                "_image_data": user_avatar_uploads_table.c.image_data,
                "_content_type": user_avatar_uploads_table.c.content_type,
                "_created_at": user_avatar_uploads_table.c.created_at,
            },
        )
