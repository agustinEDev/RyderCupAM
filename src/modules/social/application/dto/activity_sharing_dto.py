"""DTOs del interruptor de publicacion de logros."""

from pydantic import BaseModel, Field


class SetActivitySharingRequestDTO(BaseModel):
    """Peticion para encender o apagar la publicacion de logros."""

    enabled: bool = Field(
        description=(
            "Si los logros del jugador se publican en el feed de sus amigos. "
            "Apagarlo retira ademas lo ya publicado."
        )
    )


class ActivitySharingResponseDTO(BaseModel):
    """Como queda el interruptor y que se retiro al apagarlo."""

    share_activity: bool = Field(description="Estado en el que queda el interruptor")
    removed_events: int = Field(
        default=0,
        description=(
            "Cuantas entradas se retiraron del feed. Siempre 0 al encender: "
            "encender no recupera lo borrado, el feed se llena con lo que se juegue."
        ),
    )
