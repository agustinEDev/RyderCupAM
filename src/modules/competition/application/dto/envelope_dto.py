"""DTOs de los sobres (FE #655)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EnvelopeDTO(BaseModel):
    """Un sobre, con su lista dentro. Solo se devuelve a quien puede verla."""

    round_id: UUID = Field(..., description="La sesion.")
    team: str = Field(..., description="El equipo: A o B.")
    entries: list[list[UUID]] = Field(
        default_factory=list, description="Las filas, en el orden del capitan."
    )
    submitted: bool = Field(..., description="Si ya hay algo dentro.")
    submitted_at: datetime | None = Field(None, description="Cuando se entrego.")
    automatic: bool = Field(..., description="True si lo relleno la aplicacion.")


class EnvelopesViewDTO(BaseModel):
    """Lo que puede ver quien pregunta, que depende de quien sea.

    Antes de abrirlos, un capitan ve el suyo y **solo si el otro esta
    entregado**, nunca su contenido: verlo antes de tiempo es el juego entero.
    Abiertos, los ve todo el mundo.
    """

    round_id: UUID = Field(..., description="La sesion.")
    revealed: bool = Field(..., description="Si ya se abrieron.")
    team_a_submitted: bool = Field(..., description="Si el equipo A entrego.")
    team_b_submitted: bool = Field(..., description="Si el equipo B entrego.")
    team_a_automatic: bool = Field(
        False, description="Si el sobre del equipo A lo relleno la aplicacion."
    )
    team_b_automatic: bool = Field(
        False, description="Si el sobre del equipo B lo relleno la aplicacion."
    )
    mine: EnvelopeDTO | None = Field(None, description="El sobre de quien pregunta, si capitanea.")
    rival: EnvelopeDTO | None = Field(None, description="El del rival, solo si estan abiertos.")
    rival_submitted: bool = Field(False, description="Si el rival ya entrego el suyo.")
    matchups: list[list[list[UUID]]] = Field(
        default_factory=list, description="Los enfrentamientos, solo si estan abiertos."
    )


class RevealEnvelopesResponseDTO(BaseModel):
    """Lo que sale de abrir los dos sobres."""

    round_id: UUID = Field(..., description="La sesion.")
    matchups: list[list[list[UUID]]] = Field(
        default_factory=list, description="Los enfrentamientos, cruzados por posicion."
    )
    filled_automatically: list[str] = Field(
        default_factory=list, description="Los equipos cuyo sobre relleno la aplicacion."
    )
