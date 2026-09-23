"""DTOs de los sobres (FE #655)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from src.modules.competition.domain.entities.envelope import Envelope


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
    reveal_when_both_ready: bool = Field(
        False, description="Si ese capitan pidio abrirlos en cuanto esten los dos."
    )


class EnvelopePlayerDTO(BaseModel):
    """Un jugador del equipo de quien pregunta, para armar su sobre.

    Nombre y handicap, como en la sala de draft: es con lo que se ordena, y
    cualquier otro dato convertiria la decision en un informe.
    """

    user_id: UUID = Field(..., description="ID del jugador.")
    name: str = Field(..., description="Nombre con el que se le pinta.")
    handicap: Decimal | None = Field(None, description="Handicap que cuenta en esta competicion.")


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
    rival_wants_early: bool = Field(
        False, description="Si el rival pidio abrirlos sin esperar a la hora."
    )
    # Lo dice la vista y NO el cliente: la regla —hacen falta los dos sobres
    # dentro, sea quien sea— vive en un sitio, y repetirla en la pantalla es
    # justo donde se desincronizan
    can_reveal: bool = Field(False, description="Si quien pregunta puede abrirlos ahora.")
    # Idem: que el front sepa «estos formatos son de parejas» es duplicar una
    # regla del agregado. Lo que la pantalla necesita es cuantos van por fila
    players_per_row: int = Field(
        1, description="Jugadores por fila: 1 en individuales, 2 en los formatos de parejas."
    )
    # Para que la pantalla lo cuente en vez de dejar al capitan a ciegas
    reveal_scheduled_at: datetime | None = Field(
        None, description="Cuando se abren solos: 6 horas antes de la sesion."
    )
    matchups: list[list[list[UUID]]] = Field(
        default_factory=list, description="Los enfrentamientos, solo si estan abiertos."
    )
    # Los nombres viajan con la vista: de un UUID no sale ninguno, y sin esto
    # la pantalla tendria que pedir aparte las inscripciones
    my_players: list[EnvelopePlayerDTO] = Field(
        default_factory=list,
        description="Los del equipo de quien pregunta, si capitanea alguno.",
    )
    player_names: dict[str, str] = Field(
        default_factory=dict, description="Nombre de cada jugador que aparece en la vista."
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


def envelope_to_dto(sobre) -> EnvelopeDTO:
    """El sobre tal como lo ve quien puede verlo.

    Aqui y no dentro de un caso de uso: los tres lo necesitan, y tenerlo en uno
    obligaba a los otros dos a importarle una funcion privada.
    """
    return EnvelopeDTO(
        round_id=sobre.round_id.value,
        team=sobre.team,
        entries=[[uid.value for uid in fila] for fila in sobre.entries],
        submitted=sobre.is_submitted(),
        submitted_at=sobre.submitted_at,
        automatic=sobre.automatic,
        reveal_when_both_ready=sobre.reveal_when_both_ready,
    )


def matchups_to_dto(sobre_a, sobre_b) -> list[list[list[UUID]]]:
    """Los enfrentamientos, cruzados por posicion."""
    return [
        [[uid.value for uid in fila_a], [uid.value for uid in fila_b]]
        for fila_a, fila_b in Envelope.pair_up(sobre_a, sobre_b)
    ]


class ResetEnvelopesResponseDTO(BaseModel):
    """Lo que se ha llevado por delante rehacer los sobres de una sesion."""

    round_id: UUID = Field(..., description="La sesion que se ha rehecho.")
    envelopes_removed: int = Field(..., description="Sobres que se han tirado.")
    matches_removed: int = Field(
        ..., description="Partidos que se han tirado: ya no salian de ningun sobre."
    )
