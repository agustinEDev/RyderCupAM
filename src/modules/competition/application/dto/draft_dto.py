"""DTOs de la sala de draft (FE #653)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class DraftPlayerDTO(BaseModel):
    """Un jugador que se puede elegir.

    Nombre y handicap, y nada mas: es lo que el dueno del producto pidio para
    la ventana de elegir el 22 sep. Un capitan decide con eso, y cualquier otro
    dato —partidos jugados, resultados— convertiria la eleccion en un informe.
    """

    user_id: UUID = Field(..., description="ID del jugador.")
    name: str = Field(..., description="Nombre con el que se le pinta.")
    handicap: Decimal = Field(..., description="Handicap que cuenta en esta competicion.")


class DraftPickDTO(BaseModel):
    """Una eleccion ya hecha."""

    user_id: UUID = Field(..., description="A quien se eligio.")
    team: str = Field(..., description="Equipo que lo eligio: A o B.")
    order: int = Field(..., description="En que turno se eligio, empezando por 1.")
    automatic: bool = Field(
        ..., description="True si la eligio la aplicacion al agotarse el minuto."
    )


class DraftStateDTO(BaseModel):
    """La sala entera, que es lo que la pantalla pinta en directo."""

    id: UUID = Field(..., description="ID de la sala.")
    competition_id: UUID = Field(..., description="ID de la competicion.")
    status: str = Field(..., description="PENDING, IN_PROGRESS o COMPLETED.")
    first_pick: str | None = Field(None, description="Equipo que salio en el sorteo.")
    current_team: str | None = Field(None, description="Equipo al que le toca elegir.")
    turn_started_at: datetime | None = Field(None, description="Cuando empezo el turno de ahora.")
    seconds_per_turn: int = Field(..., description="Lo que dura un turno.")
    # El contador del movil se dibuja contra ESTA hora, no contra la suya: dos
    # relojes descuadrados verian minutos distintos, y el adelantado daria el
    # turno por perdido antes de tiempo
    server_time: datetime = Field(..., description="La hora del servidor al responder.")
    team_a_captain_id: UUID = Field(..., description="Capitan del equipo A.")
    team_b_captain_id: UUID = Field(..., description="Capitan del equipo B.")
    team_a: list[UUID] = Field(default_factory=list, description="Equipo A: capitan y elegidos.")
    team_b: list[UUID] = Field(default_factory=list, description="Equipo B: capitan y elegidos.")
    picks: list[DraftPickDTO] = Field(default_factory=list, description="Las elecciones, en orden.")
    available_players: list[DraftPlayerDTO] = Field(
        default_factory=list, description="Quien queda por elegir."
    )
