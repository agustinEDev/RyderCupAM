"""DTOs de las partidas de las franjas de stroke play (#251, PR 4)."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

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

    # Tantas como salidas puede tener una hoja (6:00-20:00 cada 5 min son 169)
    group_ids: list[UUID] = Field(..., max_length=200)


class TeeGroupMarkerDTO(BaseModel):
    """Quién marca a quién."""

    user_id: UUID
    marks_user_id: UUID


class TeeGroupMarkersRequestDTO(BaseModel):
    """Los marcadores de una partida: todos los jugadores, nadie a sí mismo."""

    markers: list[TeeGroupMarkerDTO] = Field(..., max_length=4)


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


class UnassignedPlayerDTO(BaseModel):
    """Alguien con plaza en la franja y sin partida: para colocarlo."""

    user_id: UUID
    name: str


class TeeGroupsResponseDTO(BaseModel):
    """Las partidas de una franja."""

    round_id: UUID
    editable: bool = Field(
        ...,
        description="Si el organizador aún puede generarlas o cambiarlas (hasta la 1.ª salida).",
    )
    unassigned_players: list[UnassignedPlayerDTO] = Field(
        ..., description="Con plaza en la franja y sin partida, por orden de llegada."
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


class TeeGroupHoleDTO(BaseModel):
    """Un hoyo de un jugador: su lado, el de su marcador y si coinciden."""

    hole: int
    par: int
    strokes_received: int = Field(..., description="Con signo: un plus los da.")
    own_score: int | None
    own_submitted: bool
    marker_score: int | None
    marker_submitted: bool
    status: str = Field(..., description="PENDING, MATCH o MISMATCH.")


class TeeGroupTotalsDTO(BaseModel):
    """Lo validado de una tarjeta."""

    thru: int = Field(..., description="Hoyos validados, en cualquier orden (P15).")
    points: int
    gross_points: int
    gross: int
    net: int
    to_par_net: int
    to_par_gross: int
    complete: bool


class TeeGroupScoringPlayerDTO(BaseModel):
    user_id: UUID
    name: str
    playing_handicap: int
    tee_color: str
    card_status: str = Field(..., description="JUGANDO, ENTREGADA, RETIRADO o NO_PRESENTADO.")
    marks_user_id: UUID | None
    marked_by_user_id: UUID | None
    holes: list[TeeGroupHoleDTO]
    totals: TeeGroupTotalsDTO


class TeeGroupScoringViewDTO(BaseModel):
    """La partida para anotar (pestaña 1) y ver las tarjetas de los suyos (pestaña 3)."""

    group_id: UUID
    round_id: UUID
    number: int
    tee_time: str
    status: str
    scoring_opens_at: datetime | None = Field(
        ..., description="La primera salida de la franja (P1); null sin zona horaria."
    )
    tournament_type: str
    picked_up_allowed: bool = Field(..., description="Stableford sí; Medal no.")
    i_mark_user_id: UUID | None = Field(..., description="A quién marca quien mira.")
    players: list[TeeGroupScoringPlayerDTO]


class CorrectHoleBodyDTO(BaseModel):
    """
    El organizador mete el lado del jugador, el del marcador o los dos (P4, P9, P11).

    Como al anotar, omitir un campo no lo toca y nulo es levantar bola (no en Medal).
    """

    own_score: int | None = Field(None, ge=1, le=15, description="El lado del jugador.")
    marker_score: int | None = Field(None, ge=1, le=15, description="El lado del marcador.")

    @model_validator(mode="after")
    def _algun_lado(self) -> "CorrectHoleBodyDTO":
        # Vacía arrancaría la partida sin un golpe y dejaría una fila que no
        # cuenta como jugada pero impide borrar la franja
        if not self.model_fields_set:
            raise ValueError("Falta own_score o marker_score")
        return self


class StandingRowDTO(BaseModel):
    """Una fila de una clasificación de stroke play."""

    position: int | None = Field(..., description="null sin puesto: sin empezar, NR o NP.")
    tied: bool = Field(..., description="Comparte puesto («T3»): no hay desempate automático.")
    user_id: UUID
    name: str
    category: int | None
    handicap: Decimal
    value: int | None = Field(
        ...,
        description="Stableford: puntos (brutos en el scratch). Medal: golpes respecto al par.",
    )
    cards: int
    thru: int
    status: str = Field(..., description="CLASIFICADO, SIN_EMPEZAR, NR o NP.")


class StandingsResponseDTO(BaseModel):
    """Una clasificación: la de una franja, la general o la scratch."""

    tournament_type: str
    scale: str = Field(..., description="NETA o SCRATCH.")
    rule: str = Field(..., description="ACCUMULATED o BEST_CARD.")
    category: int | None
    rows: list[StandingRowDTO]
    me: StandingRowDTO | None = Field(
        None, description="Scratch: la fila de quien mira si queda fuera del corte."
    )
