"""DTOs para el modulo de scoring."""

from pydantic import BaseModel, Field


class SubmitHoleScoreBodyDTO(BaseModel):
    """Body del request para registrar score de un hoyo."""

    own_score: int | None = Field(None, ge=1, le=9)
    marked_player_id: str
    marked_score: int | None = Field(None, ge=1, le=9)


class RoundInfoDTO(BaseModel):
    """Info de la ronda en scoring view."""

    id: str
    date: str
    session_type: str
    golf_course_name: str


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
    tee_category: str
    playing_handicap: int
    strokes_received: list[int]


class HoleInfoDTO(BaseModel):
    """Info de un hoyo."""

    hole_number: int
    par: int
    stroke_index: int


class PlayerHoleScoreDTO(BaseModel):
    """Score de un jugador en un hoyo."""

    user_id: str
    own_score: int | None = None
    marker_score: int | None = None
    validation_status: str
    net_score: int | None = None
    strokes_received_this_hole: int


class HoleResultDTO(BaseModel):
    """Resultado de un hoyo."""

    winner: str | None = None
    standing: str | None = None
    standing_team: str | None = None


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
    holes: list[HoleInfoDTO]
    scores: list[HoleScoreEntryDTO]
    match_standing: MatchStandingDTO
    scorecard_submitted_by: list[str]


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
