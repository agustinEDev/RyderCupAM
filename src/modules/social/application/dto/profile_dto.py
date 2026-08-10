"""DTOs del perfil de un jugador y del feed de actividad."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.modules.user.application.dto.player_stats_dto import PlayerStatsResponseDTO


class PlayerProfileResponseDTO(BaseModel):
    """
    El perfil de un jugador tal y como lo ve un amigo.

    Lleva lo justo para pintar la ficha: quien es, su avatar, su handicap y el
    mismo resumen de rendimiento que el jugador ve en su propio panel. No lleva
    correo ni nada de la cuenta: es el perfil de golf de alguien, no su ficha
    de usuario.
    """

    id: str
    first_name: str
    last_name: str
    handicap: float | None = Field(
        default=None, description="Handicap del perfil, None si aun no lo ha fijado"
    )
    avatar_source: str
    avatar_preset_id: int | None = None
    has_avatar_upload: bool = Field(
        default=False,
        description="Si tiene foto propia subida; la imagen se pide al endpoint de avatares",
    )
    stats: PlayerStatsResponseDTO = Field(
        description="El mismo resumen de rendimiento que su propio panel (BE #128, #167)"
    )


class ActivityEventDTO(BaseModel):
    """Una entrada del feed."""

    id: str
    user_id: str
    type: str
    occurred_at: datetime
    payload: dict = Field(
        default_factory=dict,
        description="El detalle propio de cada tipo: cuantos birdies, en que hoyos, que campo",
    )
    source_match_id: str = Field(description="La partida de la que sale, para enlazar al detalle")


class FeedAuthorDTO(BaseModel):
    """Quien publico una entrada, para no obligar al cliente a pedir cada perfil."""

    id: str
    first_name: str
    last_name: str
    avatar_source: str
    avatar_preset_id: int | None = None


class FeedResponseDTO(BaseModel):
    """
    Una pagina del feed, con el cursor para pedir la siguiente.

    El cursor son **dos** valores y no solo la fecha: todos los logros de una
    misma vuelta comparten `occurred_at`, asi que paginar por fecha sola se
    dejaria fuera los que aun no se han enseñado de esa vuelta.
    """

    events: list[ActivityEventDTO] = Field(default_factory=list)
    authors: dict[str, FeedAuthorDTO] = Field(
        default_factory=dict, description="Autores de esta pagina, indexados por id"
    )
    next_cursor: str | None = Field(
        default=None,
        description="Pasalo como `cursor` para la siguiente pagina. None cuando no hay mas",
    )
    unseen_count: int = Field(
        default=0, description="Cuantas entradas se han publicado desde la ultima visita"
    )
