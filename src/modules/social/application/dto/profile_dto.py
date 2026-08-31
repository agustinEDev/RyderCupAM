"""DTOs del perfil de un jugador y del feed de actividad."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.modules.user.application.dto.player_stats_dto import PlayerStatsResponseDTO


class FriendshipStateDTO(BaseModel):
    """
    En que punto esta la relacion con el jugador del perfil.

    Va en el perfil para que el cliente sepa que boton pintar sin tener que
    cruzar la lista de amigos con la de solicitudes. `PENDING_SENT` y
    `PENDING_RECEIVED` se distinguen porque no llevan al mismo sitio: una espera
    respuesta del otro, la otra pide una respuesta tuya.
    """

    status: str = Field(
        description="NONE, PENDING_SENT, PENDING_RECEIVED, ACCEPTED, DECLINED o BLOCKED"
    )
    friendship_id: str | None = Field(
        default=None,
        description=(
            "Id de la relacion, necesario para aceptarla o deshacerla. "
            "None cuando todavia no hay ninguna"
        ),
    )


class PlayerProfileResponseDTO(BaseModel):
    """
    El perfil de un jugador, con dos niveles de detalle segun quien mire.

    **Cualquiera ve la ficha minima**: nombre, apellidos y foto. Es lo que hace
    falta para encontrar a alguien por su nombre y reconocerlo antes de mandarle
    una solicitud, y no dice nada de el que no diga ya la busqueda.

    **Solo el propio jugador y sus amigos ven lo de detras**: correo, handicap,
    estadisticas y actividad. Esos campos llegan en None a cualquier otro, no
    recortados ni a cero — un cero se leeria como "juega fatal" en lugar de "no
    puedes ver esto".

    El correo esta entre amigos porque una amistad aceptada aqui es un contacto
    de verdad, y poder escribirle fuera de la aplicacion es parte de eso. Lo que
    no puede pasar —y no pasa— es que se recolecten direcciones sin relacion
    alguna: la busqueda por nombre no devuelve ninguna, y aqui hace falta que el
    otro haya aceptado.
    """

    id: str
    first_name: str
    last_name: str
    display_name: str = Field(
        default="",
        description=(
            "Nombre con el que se debe mostrar a esta persona: su alias si "
            "tiene, y si no su nombre completo."
        ),
    )
    avatar_source: str
    avatar_preset_id: int | None = None
    has_avatar_upload: bool = Field(
        default=False,
        description="Si tiene foto propia subida; la imagen se pide al endpoint de avatares",
    )
    friends_count: int = Field(
        default=0,
        description=(
            "Cuantos amigos tiene. Va en la ficha publica, como el contador de "
            "seguidores de cualquier perfil: es un numero, no dice quienes son"
        ),
    )
    friendship: FriendshipStateDTO = Field(
        description="En que punto esta tu relacion con el, para saber que boton ofrecer"
    )
    is_friend: bool = Field(
        default=False, description="Atajo de `friendship.status == ACCEPTED`"
    )
    email: str | None = Field(
        default=None,
        description=(
            "Solo uno mismo y sus amigos: una amistad aceptada es un contacto de "
            "verdad. None para cualquier otro"
        ),
    )
    handicap: float | None = Field(
        default=None,
        description=(
            "Solo uno mismo y sus amigos. None si no lo sois o si no lo ha fijado"
        ),
    )
    stats: PlayerStatsResponseDTO | None = Field(
        default=None,
        description=(
            "Solo uno mismo y sus amigos: el mismo resumen que su propio panel "
            "(BE #128, #167). None para cualquier otro"
        ),
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
    display_name: str = Field(
        default="",
        description=(
            "Nombre con el que se debe mostrar a esta persona: su alias si "
            "tiene, y si no su nombre completo."
        ),
    )
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
    courses: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Nombre de cada campo citado en esta pagina, indexado por id. "
            "El nombre va aparte y no dentro del `payload` del evento porque el "
            "payload se escribio al publicar el logro: un campo renombrado dejaria "
            "el feed contando el nombre viejo para siempre"
        ),
    )
    next_cursor: str | None = Field(
        default=None,
        description="Pasalo como `cursor` para la siguiente pagina. None cuando no hay mas",
    )
    unseen_count: int = Field(
        default=0,
        description=(
            "Cuantas entradas **de amigos** se han publicado desde la ultima visita. "
            "Los logros propios no cuentan: lo que uno acaba de hacer no es novedad "
            "para uno"
        ),
    )
