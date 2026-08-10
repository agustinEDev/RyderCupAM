"""DTOs de la galeria de fotos del perfil."""

from datetime import datetime

from pydantic import BaseModel, Field


class ProfilePhotoDTO(BaseModel):
    """
    Una foto de la galeria, **sin la imagen**.

    Los bytes no van aqui: se piden aparte, uno por foto, y el navegador los
    cachea para siempre porque una foto no cambia nunca. Meterlos en el listado
    haria que abrir un perfil moviera siete megas en base64 cada vez.
    """

    id: str
    user_id: str
    caption: str | None = None
    created_at: datetime
    url: str = Field(description="De donde bajar la imagen de esta foto")


class ProfileGalleryResponseDTO(BaseModel):
    """La galeria de un jugador."""

    photos: list[ProfilePhotoDTO] = Field(default_factory=list)
    total: int = Field(default=0, description="Cuantas fotos tiene")
    remaining_slots: int = Field(
        default=0, description="Cuantas mas puede subir antes de llegar al tope"
    )
