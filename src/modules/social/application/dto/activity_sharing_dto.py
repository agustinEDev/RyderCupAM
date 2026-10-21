"""DTOs del interruptor de publicacion de logros."""

from pydantic import BaseModel, Field


class SetActivitySharingRequestDTO(BaseModel):
    """Peticion para encender o apagar la publicacion de logros."""

    enabled: bool = Field(
        description=(
            "Si los logros del jugador se publican en el feed de sus amigos. "
            "Apagarlo se lo retira ademas a ellos de lo ya publicado; el jugador "
            "sigue viendo sus logros en su propio feed."
        )
    )


class ActivitySharingResponseDTO(BaseModel):
    """Como queda el interruptor y que se retiro al apagarlo."""

    share_activity: bool = Field(description="Estado en el que queda el interruptor")
    removed_events: int = Field(
        default=0,
        description=(
            "Cuantas entradas dejaron de ver sus amigos. Siempre 0 al encender: "
            "encender no destapa lo retirado ni lo publicado mientras estuvo apagado; "
            "sus amigos ven lo que se publique a partir de ahi."
        ),
    )
