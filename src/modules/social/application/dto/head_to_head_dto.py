"""DTOs del cara a cara y de las partidas jugadas juntos (BE-3)."""

from datetime import date

from pydantic import BaseModel, Field


class HeadToHeadRecordDTO(BaseModel):
    """Ganadas, empatadas y perdidas, desde quien mira."""

    won: int
    halved: int
    lost: int


class HeadToHeadDTO(BaseModel):
    """
    El cara a cara con un amigo, en dos apartados.

    Quien gana va por la modalidad, nunca en bruto: Stableford, mas puntos;
    match play, quien gano el partido; Medal, menos golpes netos.
    """

    against: HeadToHeadRecordDTO | None = Field(
        default=None,
        description=(
            "«Contra él»: bandos contrarios de un match play, o rivales en la misma "
            "partida de stroke play. None si no hay ninguna que contar"
        ),
    )
    alongside: HeadToHeadRecordDTO | None = Field(
        default=None,
        description=(
            "«Con él»: compañeros en el mismo partido (fourball o foursomes), con el "
            "resultado del equipo. None si no hay ninguno"
        ),
    )


class GameTogetherDTO(BaseModel):
    """Una partida terminada que jugasteis los dos."""

    kind: str = Field(description="QUICK_MATCH, TOURNAMENT_MATCH o TOURNAMENT_GROUP")
    id: str = Field(description="Id de la partida rapida, del partido o del grupo")
    played_on: date
    golf_course_id: str | None = None
    golf_course_name: str | None = None
    format: str = Field(description="SINGLES, FOURBALL, FOURSOMES, STABLEFORD o MEDAL")
    relation: str = Field(description="AGAINST (contra él) o WITH (con él)")
    result: str | None = Field(
        default=None,
        description=(
            "WON, HALVED o LOST para quien mira. None si no cuenta para el cara a "
            "cara: sin resultado o con una tarjeta a medias"
        ),
    )
    quick_match_id: str | None = Field(default=None, description="Para abrir la partida rapida")
    competition_id: str | None = Field(default=None, description="Para abrir el torneo")
    competition_name: str | None = None
    match_id: str | None = Field(
        default=None, description="El partido o el grupo dentro del torneo"
    )


class GamesTogetherPageDTO(BaseModel):
    """Una pagina de partidas juntos, de la mas reciente a la mas antigua."""

    games: list[GameTogetherDTO] = Field(default_factory=list)
    next_cursor: str | None = Field(
        default=None,
        description="Pasalo como `cursor` para ver mas. None cuando no hay mas",
    )
