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

    kind: str = Field(
        description=(
            "QUICK_MATCH, TOURNAMENT_MATCH, TOURNAMENT_GROUP o TOURNAMENT_STROKE_PLAY "
            "(un stroke play COMPLETADO entero, una sola entrada por torneo con los dos "
            "puestos de la general final; sus grupos ya no salen sueltos)"
        )
    )
    id: str = Field(
        description=(
            "Id de la partida rapida, del partido o del grupo; en TOURNAMENT_STROKE_PLAY, "
            "el del torneo"
        )
    )
    played_on: date
    golf_course_id: str | None = None
    golf_course_name: str | None = None
    format: str = Field(description="SINGLES, FOURBALL, FOURSOMES, STABLEFORD o MEDAL")
    relation: str = Field(description="AGAINST (contra él) o WITH (con él)")
    result: str | None = Field(
        default=None,
        description=(
            "WON, HALVED o LOST para quien mira; UNFINISHED o None si no cuenta. "
            "Ni UNFINISHED ni None suman en el cara a cara. "
            "PARTIDA RAPIDA STROKE PLAY: UNFINISHED si alguno de los dos no cuenta "
            "por sus hoyos (la referencia es el maximo de hoyos anotados por alguien "
            "de la partida; cuentan quienes tienen exactamente esos hoyos y al menos "
            "9; con conjuntos distintos del mismo tamaño maximo no cuenta nadie). "
            "Si los dos cuentan, None cuando no se puede juzgar: sin campo o sin "
            "modalidad. Quien no tiene hándicap juega con 0, como en la propia "
            "partida y en su aviso: la falta de hándicap ya no da None. "
            "PARTIDA RAPIDA MATCH PLAY: None si no se puede juzgar (sin campo; la "
            "falta de hándicap tampoco da None: juega con 0). Si "
            "se puede, UNFINISHED salvo que se decidiera antes de tiempo (un 3&2) o "
            "que los dos bandos entregaran los mismos hoyos, al menos 9; un hoyo es "
            "del bando en cuanto lo anota uno de sus jugadores, tambien en fourball. "
            "Incluye la partida sin ningun hoyo adjudicable. "
            "TORNEO: nunca UNFINISHED; None si el partido no tiene ganador o, en un "
            "grupo de stroke play de un torneo sin completar, si alguna de las dos "
            "tarjetas no esta entregada con los 18 hoyos validados. "
            "TOURNAMENT_STROKE_PLAY: por la general final, con el desempate por menor "
            "hándicap: delante gana, mismo puesto empata; None si alguno no quedo "
            "clasificado (retirado, NR)"
        ),
    )
    quick_match_id: str | None = Field(default=None, description="Para abrir la partida rapida")
    competition_id: str | None = Field(default=None, description="Para abrir el torneo")
    competition_name: str | None = None
    match_id: str | None = Field(
        default=None,
        description="El partido o el grupo dentro del torneo; None en TOURNAMENT_STROKE_PLAY",
    )
    # Solo en TOURNAMENT_STROKE_PLAY (tabla del 22 oct 2026, J): «4.º y 7.º de 16»
    my_position: int | None = Field(
        default=None,
        description="Mi puesto en la general final; None si no quede clasificado (NR)",
    )
    my_tied: bool | None = Field(
        default=None, description="Si comparto el puesto (mismo valor y mismo hándicap)"
    )
    their_position: int | None = Field(
        default=None, description="Su puesto en la general final; None si no quedo clasificado"
    )
    their_tied: bool | None = Field(default=None, description="Si comparte su puesto")
    total_players: int | None = Field(
        default=None, description="Filas de la general final (todos los inscritos que jugaron)"
    )


class GamesTogetherPageDTO(BaseModel):
    """Una pagina de partidas juntos, de la mas reciente a la mas antigua."""

    games: list[GameTogetherDTO] = Field(default_factory=list)
    next_cursor: str | None = Field(
        default=None,
        description="Pasalo como `cursor` para ver mas. None cuando no hay mas",
    )
