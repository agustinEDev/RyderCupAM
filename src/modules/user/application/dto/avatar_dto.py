"""
Avatar DTOs - Application Layer

DTOs de entrada/salida para los casos de uso de gestión de avatar de usuario.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SetAvatarPresetRequestDTO(BaseModel):
    """DTO de entrada para activar un avatar predefinido."""

    preset_id: int = Field(..., ge=1, le=10, description="ID del preset (1-10).")


class AvatarPresetInfoDTO(BaseModel):
    """DTO de salida: metadata de un preset de avatar disponible."""

    id: int = Field(..., description="ID del preset (1-10).")
    image_url: str = Field(..., description="URL relativa para obtener la imagen del preset.")


class AvatarUploadInfoDTO(BaseModel):
    """DTO de salida: una foto de avatar subida por el propio usuario (para el historial)."""

    id: UUID = Field(..., description="ID de la foto subida.")
    created_at: datetime = Field(..., description="Fecha y hora de subida.")
    is_active: bool = Field(..., description="True si es el avatar activo actualmente.")
    image_url: str = Field(..., description="URL relativa para obtener esta foto concreta.")
