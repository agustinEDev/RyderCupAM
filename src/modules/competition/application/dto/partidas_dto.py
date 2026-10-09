"""DTOs de las partidas de las franjas de stroke play (#251, PR 4)."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from src.modules.competition.domain.value_objects.orden_de_salida import OrdenDeSalida


class GenerateTeeGroupsRequestDTO(BaseModel):
    """Generar las partidas de una franja."""

    order: OrdenDeSalida = Field(
        ..., description="HIGH_FIRST: los hándicaps más altos salen primero; LOW_FIRST, al revés."
    )


class TeeGroupPlayerDTO(BaseModel):
    """Un jugador de una partida, con la foto que se sacó al generarla."""

    user_id: UUID
    name: str
    handicap: Decimal = Field(..., description="El hándicap fijado al cerrar las inscripciones.")
    playing_handicap: int = Field(..., description="Con signo: un plus es negativo.")
    tee_color: str
    tee_gender: str | None
    strokes_by_hole: list[int] = Field(
        ..., description="Los 18 hoyos en orden, con signo: lo que recibe (o da) en cada uno."
    )
    marks_user_id: UUID | None = Field(None, description="A quién marca; null en una partida de 1.")


class TeeGroupDTO(BaseModel):
    """Una partida de la franja."""

    id: UUID
    number: int
    tee_time: str = Field(..., description="HH:MM, hora del campo.")
    status: str
    incomplete: bool = Field(..., description="De un solo jugador, por bajas: sin marcador.")
    players: list[TeeGroupPlayerDTO]


class TeeGroupsResponseDTO(BaseModel):
    """Las partidas de una franja."""

    round_id: UUID
    editable: bool = Field(
        ...,
        description="Si el organizador aún puede generarlas o cambiarlas (hasta la 1.ª salida).",
    )
    unassigned_player_ids: list[UUID] = Field(
        ..., description="Con plaza en la franja y sin partida."
    )
    groups: list[TeeGroupDTO]
