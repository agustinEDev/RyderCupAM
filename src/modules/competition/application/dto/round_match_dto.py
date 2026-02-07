"""DTOs para Rounds, Matches y TeamAssignment - Application Layer."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.modules.competition.domain.value_objects.schedule_config_mode import ScheduleConfigMode

# ======================================================================================
# Shared Response DTOs
# ======================================================================================


class MatchPlayerResponseDTO(BaseModel):
    """DTO de respuesta para un jugador dentro de un partido."""

    user_id: UUID = Field(..., description="ID del jugador.")
    playing_handicap: int = Field(..., description="Handicap de juego calculado.")
    tee_category: str = Field(..., description="Categoría de tee usada.")
    tee_gender: str | None = Field(None, description="Género del tee usado (MALE/FEMALE/null).")
    strokes_received: list[int] = Field(
        default_factory=list, description="Hoyos donde recibe golpe."
    )

    model_config = ConfigDict(from_attributes=True)


class MatchResponseDTO(BaseModel):
    """DTO de respuesta para un partido."""

    id: UUID = Field(..., description="ID del partido.")
    round_id: UUID = Field(..., description="ID de la ronda.")
    match_number: int = Field(..., description="Número de partido en la ronda.")
    team_a_players: list[MatchPlayerResponseDTO] = Field(
        default_factory=list, description="Jugadores del equipo A."
    )
    team_b_players: list[MatchPlayerResponseDTO] = Field(
        default_factory=list, description="Jugadores del equipo B."
    )
    status: str = Field(..., description="Estado del partido.")
    handicap_strokes_given: int = Field(..., description="Golpes de ventaja.")
    strokes_given_to_team: str = Field(..., description="Equipo que recibe golpes (A/B/'').")
    result: dict | None = Field(None, description="Resultado del partido.")
    created_at: datetime = Field(..., description="Fecha de creación.")
    updated_at: datetime = Field(..., description="Fecha de actualización.")

    model_config = ConfigDict(from_attributes=True)


class RoundResponseDTO(BaseModel):
    """DTO de respuesta para una ronda/sesión."""

    id: UUID = Field(..., description="ID de la ronda.")
    competition_id: UUID = Field(..., description="ID de la competición.")
    golf_course_id: UUID = Field(..., description="ID del campo de golf.")
    round_date: date = Field(..., description="Fecha de la ronda.")
    session_type: str = Field(..., description="Tipo de sesión (MORNING/AFTERNOON/EVENING).")
    match_format: str = Field(..., description="Formato de partido (SINGLES/FOURBALL/FOURSOMES).")
    status: str = Field(..., description="Estado de la ronda.")
    handicap_mode: str | None = Field(None, description="Modo de handicap (MATCH_PLAY).")
    allowance_percentage: int | None = Field(
        None, description="Porcentaje de allowance personalizado."
    )
    effective_allowance: int = Field(..., description="Allowance efectivo (custom o WHS default).")
    matches: list[MatchResponseDTO] = Field(
        default_factory=list, description="Partidos de la ronda."
    )
    created_at: datetime = Field(..., description="Fecha de creación.")
    updated_at: datetime = Field(..., description="Fecha de actualización.")

    model_config = ConfigDict(from_attributes=True)


class TeamAssignmentResponseDTO(BaseModel):
    """DTO de respuesta para asignación de equipos."""

    id: UUID = Field(..., description="ID de la asignación.")
    competition_id: UUID = Field(..., description="ID de la competición.")
    mode: str = Field(..., description="Modo de asignación (AUTOMATIC/MANUAL).")
    team_a_player_ids: list[UUID] = Field(
        default_factory=list, description="IDs de jugadores del equipo A."
    )
    team_b_player_ids: list[UUID] = Field(
        default_factory=list, description="IDs de jugadores del equipo B."
    )
    created_at: datetime = Field(..., description="Fecha de creación.")

    model_config = ConfigDict(from_attributes=True)


class ScheduleDayDTO(BaseModel):
    """DTO para un día del schedule con sus rondas."""

    day_date: date = Field(..., alias="date", description="Fecha del día.")

    model_config = ConfigDict(populate_by_name=True)
    rounds: list[RoundResponseDTO] = Field(
        default_factory=list, description="Rondas de ese día."
    )


# ======================================================================================
# CreateRound DTOs
# ======================================================================================


class CreateRoundRequestDTO(BaseModel):
    """DTO de entrada para crear una ronda."""

    competition_id: UUID = Field(..., description="ID de la competición.")
    golf_course_id: UUID = Field(..., description="ID del campo de golf.")
    round_date: date = Field(..., description="Fecha de la ronda.")
    session_type: str = Field(..., description="Tipo de sesión (MORNING/AFTERNOON/EVENING).")
    match_format: str = Field(..., description="Formato (SINGLES/FOURBALL/FOURSOMES).")
    handicap_mode: str | None = Field(
        None, description="Modo de handicap para SINGLES (MATCH_PLAY)."
    )
    allowance_percentage: int | None = Field(
        None, ge=50, le=100, description="Porcentaje de allowance personalizado (50-100)."
    )

    @field_validator("session_type", mode="before")
    @classmethod
    def uppercase_session_type(cls, v):
        """Convierte session_type a mayúsculas."""
        if v:
            return v.upper().strip()
        return v

    @field_validator("match_format", mode="before")
    @classmethod
    def uppercase_match_format(cls, v):
        """Convierte match_format a mayúsculas."""
        if v:
            return v.upper().strip()
        return v

    @field_validator("handicap_mode", mode="before")
    @classmethod
    def uppercase_handicap_mode(cls, v):
        """Convierte handicap_mode a mayúsculas."""
        if v:
            return v.upper().strip()
        return v


class CreateRoundResponseDTO(BaseModel):
    """DTO de salida para crear una ronda."""

    id: UUID = Field(..., description="ID de la ronda creada.")
    competition_id: UUID = Field(..., description="ID de la competición.")
    status: str = Field(..., description="Estado de la ronda (PENDING_TEAMS).")
    created_at: datetime = Field(..., description="Fecha de creación.")

    model_config = ConfigDict(from_attributes=True)


class CreateRoundBodyDTO(BaseModel):
    """DTO para el body del endpoint. competition_id viene del path."""

    golf_course_id: UUID = Field(..., description="ID del campo de golf.")
    round_date: date = Field(..., description="Fecha de la ronda.")
    session_type: str = Field(..., description="Tipo de sesión.")
    match_format: str = Field(..., description="Formato de partido.")
    handicap_mode: str | None = Field(None, description="Modo de handicap.")
    allowance_percentage: int | None = Field(None, ge=50, le=100, description="Allowance.")

    @field_validator("session_type", "match_format", mode="before")
    @classmethod
    def uppercase_enums(cls, v):
        """Convierte enums a mayúsculas."""
        if v:
            return v.upper().strip()
        return v

    @field_validator("handicap_mode", mode="before")
    @classmethod
    def uppercase_handicap(cls, v):
        """Convierte handicap_mode a mayúsculas."""
        if v:
            return v.upper().strip()
        return v


# ======================================================================================
# UpdateRound DTOs
# ======================================================================================


class UpdateRoundRequestDTO(BaseModel):
    """DTO de entrada para actualizar una ronda."""

    round_id: UUID = Field(..., description="ID de la ronda a actualizar.")
    round_date: date | None = Field(None, description="Nueva fecha.")
    session_type: str | None = Field(None, description="Nuevo tipo de sesión.")
    golf_course_id: UUID | None = Field(None, description="Nuevo campo de golf.")
    match_format: str | None = Field(None, description="Nuevo formato.")
    handicap_mode: str | None = Field(None, description="Nuevo modo de handicap.")
    allowance_percentage: int | None = Field(None, ge=50, le=100, description="Nuevo allowance.")
    clear_allowance: bool = Field(
        default=False, description="Resetear allowance al default WHS."
    )

    @field_validator("session_type", "match_format", mode="before")
    @classmethod
    def uppercase_enums(cls, v):
        """Convierte enums a mayúsculas."""
        if v:
            return v.upper().strip()
        return v

    @field_validator("handicap_mode", mode="before")
    @classmethod
    def uppercase_handicap(cls, v):
        """Convierte handicap_mode a mayúsculas."""
        if v:
            return v.upper().strip()
        return v


class UpdateRoundResponseDTO(BaseModel):
    """DTO de salida para actualizar una ronda."""

    id: UUID = Field(..., description="ID de la ronda.")
    status: str = Field(..., description="Estado actual.")
    updated_at: datetime = Field(..., description="Fecha de actualización.")

    model_config = ConfigDict(from_attributes=True)


class UpdateRoundBodyDTO(BaseModel):
    """DTO para el body del endpoint. round_id viene del path."""

    round_date: date | None = Field(None, description="Nueva fecha.")
    session_type: str | None = Field(None, description="Nuevo tipo de sesión.")
    golf_course_id: UUID | None = Field(None, description="Nuevo campo de golf.")
    match_format: str | None = Field(None, description="Nuevo formato.")
    handicap_mode: str | None = Field(None, description="Nuevo modo de handicap.")
    allowance_percentage: int | None = Field(None, ge=50, le=100, description="Nuevo allowance.")
    clear_allowance: bool = Field(default=False, description="Resetear allowance.")

    @field_validator("session_type", "match_format", mode="before")
    @classmethod
    def uppercase_enums(cls, v):
        """Convierte enums a mayúsculas."""
        if v:
            return v.upper().strip()
        return v

    @field_validator("handicap_mode", mode="before")
    @classmethod
    def uppercase_handicap(cls, v):
        """Convierte handicap_mode a mayúsculas."""
        if v:
            return v.upper().strip()
        return v


# ======================================================================================
# DeleteRound DTOs
# ======================================================================================


class DeleteRoundRequestDTO(BaseModel):
    """DTO de entrada para eliminar una ronda."""

    round_id: UUID = Field(..., description="ID de la ronda a eliminar.")


class DeleteRoundResponseDTO(BaseModel):
    """DTO de salida para eliminar una ronda."""

    id: UUID = Field(..., description="ID de la ronda eliminada.")
    deleted: bool = Field(default=True, description="Confirmación de eliminación.")
    matches_deleted: int = Field(default=0, description="Partidos eliminados en cascada.")
    deleted_at: datetime = Field(..., description="Fecha de eliminación.")

    model_config = ConfigDict(from_attributes=True)


# ======================================================================================
# GetSchedule DTOs
# ======================================================================================


class GetScheduleRequestDTO(BaseModel):
    """DTO de entrada para obtener el schedule."""

    competition_id: UUID = Field(..., description="ID de la competición.")


class GetScheduleResponseDTO(BaseModel):
    """DTO de salida para el schedule completo."""

    competition_id: UUID = Field(..., description="ID de la competición.")
    days: list[ScheduleDayDTO] = Field(
        default_factory=list, description="Días del schedule con sus rondas."
    )
    total_rounds: int = Field(default=0, description="Total de rondas.")
    total_matches: int = Field(default=0, description="Total de partidos.")
    team_assignment: TeamAssignmentResponseDTO | None = Field(
        None, description="Asignación de equipos actual."
    )

    model_config = ConfigDict(from_attributes=True)


# ======================================================================================
# GetMatchDetail DTOs
# ======================================================================================


class GetMatchDetailRequestDTO(BaseModel):
    """DTO de entrada para obtener detalle de un partido."""

    match_id: UUID = Field(..., description="ID del partido.")


class GetMatchDetailResponseDTO(BaseModel):
    """DTO de salida con detalle completo de un partido."""

    id: UUID = Field(..., description="ID del partido.")
    round_id: UUID = Field(..., description="ID de la ronda.")
    match_number: int = Field(..., description="Número de partido.")
    team_a_players: list[MatchPlayerResponseDTO] = Field(
        default_factory=list, description="Jugadores equipo A."
    )
    team_b_players: list[MatchPlayerResponseDTO] = Field(
        default_factory=list, description="Jugadores equipo B."
    )
    status: str = Field(..., description="Estado del partido.")
    handicap_strokes_given: int = Field(..., description="Golpes de ventaja.")
    strokes_given_to_team: str = Field(..., description="Equipo que recibe golpes.")
    result: dict | None = Field(None, description="Resultado.")
    round_date: date | None = Field(None, description="Fecha de la ronda.")
    session_type: str | None = Field(None, description="Tipo de sesión.")
    match_format: str | None = Field(None, description="Formato de partido.")
    created_at: datetime = Field(..., description="Fecha de creación.")
    updated_at: datetime = Field(..., description="Fecha de actualización.")

    model_config = ConfigDict(from_attributes=True)


# ======================================================================================
# AssignTeams DTOs
# ======================================================================================


class AssignTeamsRequestDTO(BaseModel):
    """DTO de entrada para asignar equipos."""

    competition_id: UUID = Field(..., description="ID de la competición.")
    mode: str = Field(..., description="Modo: AUTOMATIC o MANUAL.")
    team_a_player_ids: list[UUID] | None = Field(
        None, description="IDs jugadores equipo A (solo MANUAL)."
    )
    team_b_player_ids: list[UUID] | None = Field(
        None, description="IDs jugadores equipo B (solo MANUAL)."
    )

    @field_validator("mode", mode="before")
    @classmethod
    def uppercase_mode(cls, v):
        """Convierte mode a mayúsculas."""
        if v:
            return v.upper().strip()
        return v


class AssignTeamsResponseDTO(BaseModel):
    """DTO de salida para asignación de equipos."""

    id: UUID = Field(..., description="ID de la asignación.")
    competition_id: UUID = Field(..., description="ID de la competición.")
    mode: str = Field(..., description="Modo usado.")
    team_a_player_ids: list[UUID] = Field(
        default_factory=list, description="Jugadores equipo A."
    )
    team_b_player_ids: list[UUID] = Field(
        default_factory=list, description="Jugadores equipo B."
    )
    created_at: datetime = Field(..., description="Fecha de creación.")

    model_config = ConfigDict(from_attributes=True)


class AssignTeamsBodyDTO(BaseModel):
    """DTO para el body del endpoint. competition_id viene del path."""

    mode: str = Field(..., description="Modo: AUTOMATIC o MANUAL.")
    team_a_player_ids: list[UUID] | None = Field(None, description="Jugadores equipo A.")
    team_b_player_ids: list[UUID] | None = Field(None, description="Jugadores equipo B.")

    @field_validator("mode", mode="before")
    @classmethod
    def uppercase_mode(cls, v):
        """Convierte mode a mayúsculas."""
        if v:
            return v.upper().strip()
        return v


# ======================================================================================
# GenerateMatches DTOs
# ======================================================================================


class ManualPairingDTO(BaseModel):
    """DTO para un emparejamiento manual."""

    team_a_player_ids: list[UUID] = Field(..., description="Jugadores equipo A para este match.")
    team_b_player_ids: list[UUID] = Field(..., description="Jugadores equipo B para este match.")


class GenerateMatchesRequestDTO(BaseModel):
    """DTO de entrada para generar partidos."""

    round_id: UUID = Field(..., description="ID de la ronda.")
    manual_pairings: list[ManualPairingDTO] | None = Field(
        None, description="Emparejamientos manuales (opcional)."
    )


class GenerateMatchesResponseDTO(BaseModel):
    """DTO de salida para generar partidos."""

    round_id: UUID = Field(..., description="ID de la ronda.")
    matches_generated: int = Field(..., description="Número de partidos generados.")
    round_status: str = Field(..., description="Nuevo estado de la ronda (SCHEDULED).")

    model_config = ConfigDict(from_attributes=True)


class GenerateMatchesBodyDTO(BaseModel):
    """DTO para el body del endpoint. round_id viene del path."""

    manual_pairings: list[ManualPairingDTO] | None = Field(
        None, description="Emparejamientos manuales."
    )


# ======================================================================================
# ConfigureSchedule DTOs
# ======================================================================================


class ConfigureScheduleRequestDTO(BaseModel):
    """DTO de entrada para configurar el schedule."""

    competition_id: UUID = Field(..., description="ID de la competición.")
    mode: ScheduleConfigMode = Field(..., description="Modo: AUTOMATIC o MANUAL.")
    total_sessions: int | None = Field(
        None, ge=1, le=18, description="Total de sesiones (solo AUTO)."
    )
    sessions_per_day: int | None = Field(
        None, ge=1, le=3, description="Sesiones por día (solo AUTO)."
    )


class ConfigureScheduleResponseDTO(BaseModel):
    """DTO de salida para configurar el schedule."""

    competition_id: UUID = Field(..., description="ID de la competición.")
    mode: str = Field(..., description="Modo configurado.")
    rounds_created: int = Field(default=0, description="Rondas creadas (solo AUTO).")
    message: str = Field(..., description="Mensaje descriptivo.")

    model_config = ConfigDict(from_attributes=True)


class ConfigureScheduleBodyDTO(BaseModel):
    """DTO para el body del endpoint. competition_id viene del path."""

    mode: ScheduleConfigMode = Field(..., description="Modo: AUTOMATIC o MANUAL.")
    total_sessions: int | None = Field(None, ge=1, le=18, description="Total sesiones.")
    sessions_per_day: int | None = Field(None, ge=1, le=3, description="Sesiones por día.")


# ======================================================================================
# UpdateMatchStatus DTOs
# ======================================================================================


class UpdateMatchStatusRequestDTO(BaseModel):
    """DTO de entrada para actualizar estado de un partido."""

    match_id: UUID = Field(..., description="ID del partido.")
    action: str = Field(..., description="Acción: START o COMPLETE.")
    result: dict | None = Field(None, description="Resultado (solo para COMPLETE).")

    @field_validator("action", mode="before")
    @classmethod
    def uppercase_action(cls, v):
        """Convierte action a mayúsculas."""
        if v:
            return v.upper().strip()
        return v


class UpdateMatchStatusResponseDTO(BaseModel):
    """DTO de salida para actualizar estado."""

    match_id: UUID = Field(..., description="ID del partido.")
    new_status: str = Field(..., description="Nuevo estado del partido.")
    round_status: str | None = Field(None, description="Estado actual de la ronda (si cambió).")
    updated_at: datetime = Field(..., description="Fecha de actualización.")

    model_config = ConfigDict(from_attributes=True)


class UpdateMatchStatusBodyDTO(BaseModel):
    """DTO para el body del endpoint. match_id viene del path."""

    action: str = Field(..., description="Acción: START o COMPLETE.")
    result: dict | None = Field(None, description="Resultado (solo COMPLETE).")

    @field_validator("action", mode="before")
    @classmethod
    def uppercase_action(cls, v):
        """Convierte action a mayúsculas."""
        if v:
            return v.upper().strip()
        return v


# ======================================================================================
# DeclareWalkover DTOs
# ======================================================================================


class DeclareWalkoverRequestDTO(BaseModel):
    """DTO de entrada para declarar walkover."""

    match_id: UUID = Field(..., description="ID del partido.")
    winning_team: str = Field(..., description="Equipo ganador: A o B.")
    reason: str | None = Field(None, max_length=500, description="Razón del walkover.")

    @field_validator("winning_team", mode="before")
    @classmethod
    def uppercase_winning_team(cls, v):
        """Convierte winning_team a mayúsculas."""
        if v:
            return v.upper().strip()
        return v


class DeclareWalkoverResponseDTO(BaseModel):
    """DTO de salida para declarar walkover."""

    match_id: UUID = Field(..., description="ID del partido.")
    new_status: str = Field(..., description="Nuevo estado (WALKOVER).")
    winning_team: str = Field(..., description="Equipo ganador.")
    round_status: str | None = Field(None, description="Estado de la ronda (si cambió).")
    updated_at: datetime = Field(..., description="Fecha de actualización.")

    model_config = ConfigDict(from_attributes=True)


class DeclareWalkoverBodyDTO(BaseModel):
    """DTO para el body del endpoint. match_id viene del path."""

    winning_team: str = Field(..., description="Equipo ganador: A o B.")
    reason: str | None = Field(None, max_length=500, description="Razón.")

    @field_validator("winning_team", mode="before")
    @classmethod
    def uppercase_winning_team(cls, v):
        """Convierte winning_team a mayúsculas."""
        if v:
            return v.upper().strip()
        return v


# ======================================================================================
# ReassignMatchPlayers DTOs
# ======================================================================================


class ReassignMatchPlayersRequestDTO(BaseModel):
    """DTO de entrada para reasignar jugadores de un partido."""

    match_id: UUID = Field(..., description="ID del partido.")
    team_a_player_ids: list[UUID] = Field(..., description="Nuevos jugadores equipo A.")
    team_b_player_ids: list[UUID] = Field(..., description="Nuevos jugadores equipo B.")


class ReassignMatchPlayersResponseDTO(BaseModel):
    """DTO de salida para reasignación."""

    match_id: UUID = Field(..., description="ID del partido.")
    new_status: str = Field(..., description="Estado del partido.")
    handicap_strokes_given: int = Field(..., description="Nuevos golpes de ventaja.")
    strokes_given_to_team: str = Field(default="", description="Equipo que recibe golpes (A/B/'').")
    updated_at: datetime = Field(..., description="Fecha de actualización.")

    model_config = ConfigDict(from_attributes=True)


class ReassignMatchPlayersBodyDTO(BaseModel):
    """DTO para el body del endpoint. match_id viene del path."""

    team_a_player_ids: list[UUID] = Field(..., description="Nuevos jugadores equipo A.")
    team_b_player_ids: list[UUID] = Field(..., description="Nuevos jugadores equipo B.")
