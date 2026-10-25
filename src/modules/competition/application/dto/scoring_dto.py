"""DTOs para el modulo de scoring."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class SubmitHoleScoreBodyDTO(BaseModel):
    """
    Body del request para registrar score de un hoyo.

    **Omitir un score no es lo mismo que mandarlo nulo** (#301). Nulo es un hoyo
    recogido —conceder el hoyo, en match play—, y un campo que no viene es un
    campo que el jugador no ha tocado: el caso de uso mira `model_fields_set` y
    solo actualiza los que llegan. Mandar los dos siempre concedia el hoyo del
    jugador marcado sin que nadie lo concediera.

    **Cuidado al reconstruir este DTO**: `model_fields_set` es procedencia, no
    dato. Rehacerlo desde un volcado —`SubmitHoleScoreBodyDTO(**body.model_dump())`,
    como haria un endpoint de sincronizacion por lotes o un camino de admin que
    recomponga el body— marca los cuatro campos como enviados y vuelve a conceder
    el hoyo, sin que falle ningun test. Si hace falta reenviar este body, pasar
    `body.model_dump(exclude_unset=True)`.
    """

    own_score: int | None = Field(None, ge=1, le=15)
    # Opcional desde el 25 oct 2026: en un fourball con un retirado, el rival que
    # le marcaba ya no marca a nadie y tiene que poder anotar su propia bola. Sin
    # el, solo se guarda el golpe propio
    marked_player_id: str | None = None
    marked_score: int | None = Field(None, ge=1, le=15)
    acting_as: UUID | None = Field(
        None,
        description="Solo admin: ID del jugador al que se representa para registrar su score.",
    )

    @field_validator("marked_player_id")
    @classmethod
    def _vacio_es_ninguno(cls, valor: str | None) -> str | None:
        """Un texto vacío es no mandarlo: sin marcado (code-review)."""
        return valor or None

    @model_validator(mode="after")
    def _marcado_con_su_jugador(self) -> "SubmitHoleScoreBodyDTO":
        """Un golpe de marcador dice de quien es: sin eso no se sabe a quien va."""
        if "marked_score" in self.model_fields_set and not self.marked_player_id:
            raise ValueError("marked_score requires marked_player_id")
        return self


class RoundInfoDTO(BaseModel):
    """Info de la ronda en scoring view."""

    id: str
    date: str
    session_type: str
    golf_course_name: str
    golf_course_id: UUID = Field(..., description="Campo de la ronda: para pedir su mapa de hoyos")
    golf_course_country_code: str | None = Field(
        default=None,
        description="País del campo (ISO 3166-1 alfa-2): el mapa solo tiene imagen en España; null si no está",
    )


class MarkerAssignmentResponseDTO(BaseModel):
    """Asignacion de marcador en la respuesta."""

    scorer_user_id: str
    scorer_name: str
    marks_user_id: str
    marks_name: str
    marked_by_user_id: str
    marked_by_name: str


class ScoringPlayerDTO(BaseModel):
    """Jugador en la vista de scoring."""

    user_id: str
    user_name: str
    team: str
    tee_color: str
    tee_gender: str | None = Field(
        None,
        description=(
            "Sexo de la barra del jugador (MALE/FEMALE), null en una barra sin sexo: "
            "con el color, el mapa de hoyos envía las muestras por barra."
        ),
    )
    playing_handicap: int
    strokes_received: list[int]
    # El par, el índice y los metros son de la barra de cada jugador, no del
    # campo: en 56 de los 800 campos federados el índice cambia de una barra a
    # otra y en 25 el par. Se manda resuelto para que el cliente no tenga que
    # volver a resolverlo — y no lo resuelva de otra manera.
    hole_card: list["HoleInfoDTO"] = []


class HoleInfoDTO(BaseModel):
    """Info de un hoyo, tal y como se juega desde una salida concreta."""

    hole_number: int
    par: int
    stroke_index: int
    meters: int | None = None


class PlayerHoleScoreDTO(BaseModel):
    """Score de un jugador en un hoyo."""

    user_id: str
    own_score: int | None = None
    own_submitted: bool = False
    marker_score: int | None = None
    marker_submitted: bool = False
    validation_status: str
    net_score: int | None = None
    strokes_received_this_hole: int


class HoleResultDTO(BaseModel):
    """Resultado de un hoyo."""

    winner: str | None = None
    standing: str | None = None
    standing_team: str | None = None
    best_ball_player_a: list[str] = []
    best_ball_player_b: list[str] = []


class HoleScoreEntryDTO(BaseModel):
    """Entrada completa de un hoyo con scores y resultado."""

    hole_number: int
    player_scores: list[PlayerHoleScoreDTO]
    hole_result: HoleResultDTO | None = None


class MatchStandingDTO(BaseModel):
    """Standing actual del partido."""

    status: str
    leading_team: str | None = None
    holes_played: int
    holes_remaining: int


class DecidedResultDTO(BaseModel):
    """Resultado de partido decidido."""

    winner: str
    score: str


class ScoringViewResponseDTO(BaseModel):
    """Respuesta completa de la vista de scoring."""

    match_id: str
    match_number: int
    match_format: str
    match_status: str
    is_decided: bool
    decided_result: DecidedResultDTO | None = None
    round_info: RoundInfoDTO
    competition_id: str
    team_a_name: str
    team_b_name: str
    marker_assignments: list[MarkerAssignmentResponseDTO]
    players: list[ScoringPlayerDTO]
    # Tarjeta de referencia del campo (la de la primera salida con tarjeta).
    # Sirve para saber qué hoyos se juegan; lo que se pinta y con lo que se
    # puntúa a un jugador es su `hole_card`. Se retira cuando el cliente deje
    # de leerla.
    holes: list[HoleInfoDTO]
    scores: list[HoleScoreEntryDTO]
    match_standing: MatchStandingDTO
    scorecard_submitted_by: list[str]
    # Fourball: los jugadores retirados. Su bola ya no cuenta en lo que no
    # tenian validado y no entregan tarjeta; las asignaciones ya vienen sin
    # ellos (su pareja marca al rival que marcaban)
    withdrawn_player_ids: list[str] = Field(default_factory=list)
    # A que hora abre la anotacion de este partido, con su desfase (BE #305).
    # El cliente la usa para ofrecer «Anotar» —tambien sin cobertura, desde lo
    # que tenga guardado— en vez de adivinar si alguien pulso START. `None` en
    # rondas sin fecha o sin sesion, que solo abren con START
    scoring_opens_at: datetime | None = None


class ScorecardResultDTO(BaseModel):
    """Resultado del partido en submit scorecard."""

    winner: str | None = None
    score: str | None = None
    team_a_points: float
    team_b_points: float


class ScorecardStatsDTO(BaseModel):
    """Estadisticas del jugador en submit scorecard."""

    player_gross_total: int | None = None
    player_net_total: int | None = None
    holes_won: int
    holes_lost: int
    holes_halved: int


class SubmitScorecardResponseDTO(BaseModel):
    """Respuesta al entregar tarjeta."""

    match_id: str
    submitted_by: str
    result: ScorecardResultDTO
    stats: ScorecardStatsDTO
    match_complete: bool


class WithdrawalResponseDTO(BaseModel):
    """Respuesta al retirar a un jugador del fourball o deshacerlo (25 oct 2026)."""

    match_id: str
    withdrawn_player_ids: list[str]
    decided_result: DecidedResultDTO | None = None


class ConcedeMatchBodyDTO(BaseModel):
    """Body del request para conceder un partido."""

    conceding_team: str
    reason: str | None = None


class LeaderboardPlayerDTO(BaseModel):
    """Jugador en el leaderboard."""

    user_id: str
    user_name: str


class LeaderboardMatchDTO(BaseModel):
    """Partido en el leaderboard."""

    match_id: str
    match_number: int
    match_format: str
    # De qué sesión es: con varias, el número de partido se repite (BE #388).
    # Opcionales porque las rondas de antes no tenían fecha ni sesión
    round_date: date | None = None
    session_type: str | None = None
    status: str
    current_hole: int | None = None
    standing: str | None = None
    leading_team: str | None = None
    team_a_players: list[LeaderboardPlayerDTO]
    team_b_players: list[LeaderboardPlayerDTO]
    result: DecidedResultDTO | None = None


class LeaderboardResponseDTO(BaseModel):
    """Respuesta del leaderboard."""

    competition_id: str
    competition_name: str
    team_a_name: str
    team_b_name: str
    team_a_points: float
    team_b_points: float
    matches: list[LeaderboardMatchDTO]
