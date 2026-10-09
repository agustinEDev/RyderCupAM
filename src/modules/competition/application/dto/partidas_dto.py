"""DTOs de las partidas de las franjas de stroke play (#251, PR 4)."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from src.modules.competition.domain.value_objects.orden_de_salida import OrdenDeSalida


class GenerateTeeGroupsRequestDTO(BaseModel):
    """Generar las partidas de una franja."""

    order: OrdenDeSalida = Field(
        ..., description="HIGH_FIRST: los hándicaps más altos salen primero; LOW_FIRST, al revés."
    )


class MoveTeeGroupPlayerRequestDTO(BaseModel):
    """Mover a un jugador a otra partida, intercambiando o a una nueva al final."""

    user_id: UUID = Field(..., description="Quién se mueve.")
    group_id: UUID | None = Field(
        None, description="La partida de destino; null para una nueva al final."
    )
    swap_with_user_id: UUID | None = Field(
        None, description="Con quién de la de destino se intercambia, si está llena."
    )


class ReorderTeeGroupsRequestDTO(BaseModel):
    """El orden de salida: todas las partidas de la franja, una vez."""

    group_ids: list[UUID]


class TeeGroupMarkerDTO(BaseModel):
    """Quién marca a quién."""

    user_id: UUID
    marks_user_id: UUID


class TeeGroupMarkersRequestDTO(BaseModel):
    """Los marcadores de una partida: todos los jugadores, nadie a sí mismo."""

    markers: list[TeeGroupMarkerDTO]


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


class MyTeeGroupDTO(BaseModel):
    """Una partida mía: en qué franja y día, y la partida con mis compañeros."""

    round_id: UUID
    round_date: date
    session_type: str
    group: TeeGroupDTO


class MyTeeGroupsResponseDTO(BaseModel):
    """Mis partidas en una competición, por día y hora de salida."""

    groups: list[MyTeeGroupDTO]
