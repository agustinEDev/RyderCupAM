# -*- coding: utf-8 -*-
"""DTOs para el módulo Competition - Application Layer."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Descripciones reutilizables para campos
COMPETITION_NAME_DESC = "Nombre de la competición."
MAX_PLAYERS_DESC = "Número máximo de jugadores."
COMPETITION_ID_DESC = "ID de la competición."
# Descripciones para nombres de equipos
TEAM_1_NAME_DESC = "Nombre del equipo 1."
TEAM_2_NAME_DESC = "Nombre del equipo 2."


# Import shared DTOs
# CountryResponseDTO definido aquí para evitar importación circular
class CountryResponseDTO(BaseModel):
    """DTO de respuesta para un país."""
    code: str = Field(..., description="Código ISO 3166-1 alpha-2 del país")
    name_en: str = Field(..., description="Nombre en inglés")
    name_es: str = Field(..., description="Nombre en español")


class CreatorDTO(BaseModel):
    """
    DTO para representar información básica del creador de una competición.

    Se utiliza como objeto nested dentro de CompetitionResponseDTO
    para evitar múltiples llamadas API desde el frontend.

    Campos incluidos:
    - Datos personales: id, first_name, last_name, email
    - Datos de juego: handicap, country_code
    """
    id: UUID = Field(..., description="ID único del usuario creador")
    first_name: str = Field(..., description="Nombre del creador")
    last_name: str = Field(..., description="Apellido del creador")
    email: str = Field(..., description="Email del creador")
    handicap: float | None = Field(None, description="Handicap actual del creador")
    country_code: str | None = Field(None, description="Código ISO del país del creador")

    model_config = ConfigDict(from_attributes=True)


# ======================================================================================
# DTO para el Caso de Uso: Crear Competition
# ======================================================================================

class CreateCompetitionRequestDTO(BaseModel):
    """
    DTO de entrada para el caso de uso de creación de competición.
    Define los datos necesarios para crear un nuevo torneo.
    """
    model_config = ConfigDict(
        populate_by_name=True,  # Permite usar aliases
    )

    name: str = Field(..., min_length=3, max_length=100, description=COMPETITION_NAME_DESC)
    start_date: date = Field(..., description="Fecha de inicio del torneo.")
    end_date: date = Field(..., description="Fecha de fin del torneo.")

    # Location
    main_country: str = Field(..., min_length=2, max_length=2, description="Código ISO del país principal (ej: 'ES').")
    adjacent_country_1: str | None = Field(None, min_length=2, max_length=2, description="Código ISO del país adyacente 1 (opcional).")
    adjacent_country_2: str | None = Field(None, min_length=2, max_length=2, description="Código ISO del país adyacente 2 (opcional).")
    # Campo adicional para compatibilidad con frontend (se convierte automáticamente)
    countries: list[str] | None = Field(None, description="Lista de países adyacentes (formato frontend).")

    # Handicap Settings
    handicap_type: str = Field(..., description="Tipo de hándicap: 'SCRATCH' o 'PERCENTAGE'.")
    handicap_percentage: int | None = Field(None, ge=90, le=100, description="Porcentaje de hándicap (90, 95 o 100). Requerido si type='PERCENTAGE'.")

    # Competition Config - con alias para compatibilidad con frontend
    max_players: int = Field(default=24, ge=2, le=100, description=MAX_PLAYERS_DESC, alias="number_of_players")
    team_assignment: str = Field(default="MANUAL", description="Asignación de equipos: 'MANUAL' o 'AUTOMATIC'.")

    # Nombres de equipos (opcional, pero recomendado)
    team_1_name: str = Field(default="Team 1", min_length=3, max_length=50, description=TEAM_1_NAME_DESC)
    team_2_name: str = Field(default="Team 2", min_length=3, max_length=50, description=TEAM_2_NAME_DESC)

    @field_validator('main_country', 'adjacent_country_1', 'adjacent_country_2', mode='before')
    @classmethod
    def uppercase_country_codes(cls, v):
        """Convierte códigos de país a mayúsculas."""
        if v:
            return v.upper().strip()
        return v

    @field_validator('handicap_type', mode='before')
    @classmethod
    def uppercase_handicap_type(cls, v):
        """Convierte handicap_type a mayúsculas."""
        if v:
            return v.upper().strip()
        return v

    @field_validator('team_assignment', mode='before')
    @classmethod
    def uppercase_team_assignment(cls, v):
        """Convierte team_assignment a mayúsculas."""
        if v:
            return v.upper().strip()
        return v

    @field_validator('countries', mode='before')
    @classmethod
    def uppercase_countries(cls, v):
        """Convierte códigos de países adyacentes a mayúsculas."""
        if v and isinstance(v, list):
            return [country.upper().strip() for country in v]
        return v

    @model_validator(mode='after')
    def validate_and_convert_countries(self) -> 'CreateCompetitionRequestDTO':
        """Convierte el campo countries del frontend a adjacent_country_1/2 si es necesario."""
        # Si se proporcionó countries pero no adjacent_country_1/2, convertir
        if self.countries and not self.adjacent_country_1 and not self.adjacent_country_2:
            if len(self.countries) > 0:
                self.adjacent_country_1 = self.countries[0]
            if len(self.countries) > 1:
                self.adjacent_country_2 = self.countries[1]

        return self

    @model_validator(mode='after')
    def validate_handicap_config(self) -> 'CreateCompetitionRequestDTO':
        """Validaciones post-inicialización."""
        # Validar fechas
        if self.start_date >= self.end_date:
            raise ValueError("start_date debe ser anterior a end_date")

        # Validar handicap_type
        if self.handicap_type not in ["SCRATCH", "PERCENTAGE"]:
            raise ValueError("handicap_type debe ser 'SCRATCH' o 'PERCENTAGE'")

        # Si es PERCENTAGE, handicap_percentage es obligatorio
        if self.handicap_type == "PERCENTAGE" and self.handicap_percentage is None:
            raise ValueError("handicap_percentage es requerido cuando handicap_type='PERCENTAGE'")

        # Si es SCRATCH, handicap_percentage debe ser None
        if self.handicap_type == "SCRATCH" and self.handicap_percentage is not None:
            raise ValueError("handicap_percentage debe ser None cuando handicap_type='SCRATCH'")

        # Validar team_assignment
        if self.team_assignment not in ["MANUAL", "AUTOMATIC"]:
            raise ValueError("team_assignment debe ser 'MANUAL' o 'AUTOMATIC'")

        return self


class CreateCompetitionResponseDTO(BaseModel):
    """
    DTO de salida para el caso de uso de creación de competición.
    Devuelve la competición completa recién creada (mismo formato que CompetitionResponseDTO).
    """
    id: UUID = Field(..., description="ID único de la competición.")
    creator_id: UUID = Field(..., description="ID del usuario creador.")
    creator: CreatorDTO | None = Field(None, description="Información completa del creador.")
    name: str = Field(..., description=COMPETITION_NAME_DESC)
    status: str = Field(..., description="Estado de la competición (DRAFT al crear).")

    # Dates
    start_date: date = Field(..., description="Fecha de inicio.")
    end_date: date = Field(..., description="Fecha de fin.")

    # Location
    country_code: str = Field(..., description="Código ISO del país principal.")
    secondary_country_code: str | None = Field(None, description="Código ISO del país secundario.")
    tertiary_country_code: str | None = Field(None, description="Código ISO del país terciario.")
    location: str = Field(..., description="Ubicación formateada legible.")
    countries: list[CountryResponseDTO] = Field(default_factory=list, description="Lista de países participantes con códigos y nombres.")

    # Handicap
    handicap_type: str = Field(..., description="Tipo de hándicap.")
    handicap_percentage: int | None = Field(None, description="Porcentaje de hándicap.")

    # Nombres de equipos
    team_1_name: str = Field(..., description=TEAM_1_NAME_DESC)
    team_2_name: str = Field(..., description=TEAM_2_NAME_DESC)

    # Config
    max_players: int = Field(..., description=MAX_PLAYERS_DESC)
    team_assignment: str = Field(..., description="Tipo de asignación de equipos.")

    # Campos calculados
    is_creator: bool = Field(default=True, description="Siempre True para el creador.")
    enrolled_count: int = Field(default=0, description="Siempre 0 al crear.")

    # Timestamps
    created_at: datetime = Field(..., description="Fecha y hora de creación.")
    updated_at: datetime = Field(..., description="Fecha y hora de última actualización.")

    model_config = ConfigDict(from_attributes=True)


# ======================================================================================
# DTO para el Caso de Uso: Actualizar Competition
# ======================================================================================

class UpdateCompetitionRequestDTO(BaseModel):
    """
    DTO de entrada para el caso de uso de actualización de competición.
    Todos los campos son opcionales (actualización parcial).
    Solo permitido en estado DRAFT.
    """
    name: str | None = Field(None, min_length=3, max_length=100, description="Nuevo nombre de la competición.")
    start_date: date | None = Field(None, description="Nueva fecha de inicio.")
    end_date: date | None = Field(None, description="Nueva fecha de fin.")

    # Location
    main_country: str | None = Field(None, min_length=2, max_length=2, description="Nuevo país principal.")
    adjacent_country_1: str | None = Field(None, min_length=2, max_length=2, description="Nuevo país adyacente 1.")
    adjacent_country_2: str | None = Field(None, min_length=2, max_length=2, description="Nuevo país adyacente 2.")

    # Handicap Settings
    handicap_type: str | None = Field(None, description="Nuevo tipo de hándicap.")
    handicap_percentage: int | None = Field(None, ge=90, le=100, description="Nuevo porcentaje de hándicap.")

    # Competition Config
    max_players: int | None = Field(None, ge=2, le=100, description="Nuevo máximo de jugadores.")
    team_assignment: str | None = Field(None, description="Nueva asignación de equipos.")
    team_1_name: str | None = Field(None, min_length=3, max_length=50, description="Nuevo nombre del equipo 1.")
    team_2_name: str | None = Field(None, min_length=3, max_length=50, description="Nuevo nombre del equipo 2.")

    @field_validator('main_country', 'adjacent_country_1', 'adjacent_country_2', mode='before')
    @classmethod
    def uppercase_country_codes(cls, v):
        """Convierte códigos de país a mayúsculas."""
        if v:
            return v.upper().strip()
        return v

    @field_validator('handicap_type', mode='before')
    @classmethod
    def uppercase_handicap_type(cls, v):
        """Convierte handicap_type a mayúsculas."""
        if v:
            return v.upper().strip()
        return v

    @field_validator('team_assignment', mode='before')
    @classmethod
    def uppercase_team_assignment(cls, v):
        """Convierte team_assignment a mayúsculas."""
        if v:
            return v.upper().strip()
        return v


class UpdateCompetitionResponseDTO(BaseModel):
    """
    DTO de salida para el caso de uso de actualización de competición.
    """
    id: UUID = Field(..., description=COMPETITION_ID_DESC)
    name: str = Field(..., description="Nombre actualizado.")
    updated_at: datetime = Field(..., description="Fecha y hora de actualización.")

    model_config = ConfigDict(from_attributes=True)


# ======================================================================================
# DTO de Respuesta Genérico para Competition
# ======================================================================================

class CompetitionResponseDTO(BaseModel):
    """
    DTO de salida genérico para representar una competición.
    Se utiliza para listar competiciones y consultas detalladas.

    NOTA: Este DTO incluye campos calculados dinámicamente que NO existen
    en la entidad de dominio (is_creator, enrolled_count, location_formatted, creator).
    Estos se deben calcular en la capa de aplicación antes de construir el DTO.
    """
    id: UUID = Field(..., description=COMPETITION_ID_DESC)
    creator_id: UUID = Field(..., description="ID del usuario creador.")
    creator: CreatorDTO | None = Field(None, description="Información completa del creador.")
    name: str = Field(..., description=COMPETITION_NAME_DESC)
    status: str = Field(..., description="Estado actual (DRAFT, ACTIVE, CLOSED, etc.).")

    # Dates
    start_date: date = Field(..., description="Fecha de inicio.")
    end_date: date = Field(..., description="Fecha de fin.")

    # Location - Raw country codes (para backward compatibility con tests)
    country_code: str = Field(..., description="Código ISO del país principal.")
    secondary_country_code: str | None = Field(None, description="Código ISO del país secundario.")
    tertiary_country_code: str | None = Field(None, description="Código ISO del país terciario.")

    # Location - Formatted string (NUEVO - requerido por frontend)
    location: str = Field(..., description="Ubicación formateada legible (ej: 'Spain, France, Italy').")

    # Location - Countries array (NUEVO - requerido por frontend)
    countries: list[CountryResponseDTO] = Field(default_factory=list, description="Lista de países participantes con códigos y nombres.")

    # Handicap Settings
    handicap_type: str = Field(..., description="Tipo de hándicap: 'SCRATCH' o 'PERCENTAGE'.")
    handicap_percentage: int | None = Field(None, description="Porcentaje de hándicap (90-100) si es PERCENTAGE.")

    # Nombres de equipos
    team_1_name: str = Field(default="Team 1", description=TEAM_1_NAME_DESC)
    team_2_name: str = Field(default="Team 2", description=TEAM_2_NAME_DESC)

    # Config
    max_players: int = Field(..., description=MAX_PLAYERS_DESC)
    team_assignment: str = Field(..., description="Tipo de asignación de equipos.")

    # Campos calculados (NUEVO - requeridos por frontend)
    is_creator: bool = Field(..., description="True si el usuario autenticado es el creador de esta competición.")
    enrolled_count: int = Field(default=0, description="Número de jugadores con enrollment status APPROVED.")
    pending_enrollments_count: int = Field(default=0, description="Número de solicitudes con enrollment status PENDING (solo visible para el creador).")
    user_enrollment_status: str | None = Field(None, description="Estado de inscripción del usuario actual (REQUESTED, APPROVED, REJECTED, etc.). None si no está inscrito.")

    # Timestamps
    created_at: datetime = Field(..., description="Fecha y hora de creación.")
    updated_at: datetime = Field(..., description="Fecha y hora de última actualización.")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("id", "creator_id", mode="before")
    @classmethod
    def convert_value_objects_uuid(cls, v):
        """Convierte Value Objects UUID a UUID primitivo."""
        if hasattr(v, "value"):
            return v.value
        return v

    @field_validator("name", mode="before")
    @classmethod
    def convert_competition_name(cls, v):
        """Convierte CompetitionName a string."""
        if hasattr(v, "value"):
            return v.value
        return v

    @field_validator("status", mode="before")
    @classmethod
    def convert_competition_status(cls, v):
        """Convierte CompetitionStatus enum a string."""
        if hasattr(v, "value"):
            return v.value
        return v


# ======================================================================================
# DTOs para Transiciones de Estado del Ciclo de Vida
# ======================================================================================

# --------------------------------------------------------------------------------------
# Activate Competition (DRAFT → ACTIVE)
# --------------------------------------------------------------------------------------

class ActivateCompetitionRequestDTO(BaseModel):
    """
    DTO de entrada para activar una competición.
    Transición: DRAFT → ACTIVE (abre inscripciones).

    Solo el creador puede activar la competición.
    """
    competition_id: UUID = Field(..., description=COMPETITION_ID_DESC)


class ActivateCompetitionResponseDTO(BaseModel):
    """
    DTO de salida para activación de competición.
    """
    id: UUID = Field(..., description=COMPETITION_ID_DESC)
    status: str = Field(..., description="Nuevo estado (ACTIVE).")
    activated_at: datetime = Field(..., description="Fecha y hora de activación.")

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------------------
# Close Enrollments (ACTIVE → CLOSED)
# --------------------------------------------------------------------------------------

class CloseEnrollmentsRequestDTO(BaseModel):
    """
    DTO de entrada para cerrar inscripciones de una competición.
    Transición: ACTIVE → CLOSED (cierra inscripciones).

    Solo el creador puede cerrar las inscripciones.
    """
    competition_id: UUID = Field(..., description=COMPETITION_ID_DESC)


class CloseEnrollmentsResponseDTO(BaseModel):
    """
    DTO de salida para cierre de inscripciones.
    """
    id: UUID = Field(..., description=COMPETITION_ID_DESC)
    status: str = Field(..., description="Nuevo estado (CLOSED).")
    total_enrollments: int = Field(..., description="Número total de inscripciones aprobadas.")
    closed_at: datetime = Field(..., description="Fecha y hora de cierre.")

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------------------
# Start Competition (CLOSED → IN_PROGRESS)
# --------------------------------------------------------------------------------------

class StartCompetitionRequestDTO(BaseModel):
    """
    DTO de entrada para iniciar una competición.
    Transición: CLOSED → IN_PROGRESS (inicia el torneo).

    Solo el creador puede iniciar la competición.
    """
    competition_id: UUID = Field(..., description=COMPETITION_ID_DESC)


class StartCompetitionResponseDTO(BaseModel):
    """
    DTO de salida para inicio de competición.
    """
    id: UUID = Field(..., description=COMPETITION_ID_DESC)
    status: str = Field(..., description="Nuevo estado (IN_PROGRESS).")
    started_at: datetime = Field(..., description="Fecha y hora de inicio.")

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------------------
# Complete Competition (IN_PROGRESS → COMPLETED)
# --------------------------------------------------------------------------------------

class CompleteCompetitionRequestDTO(BaseModel):
    """
    DTO de entrada para completar/finalizar una competición.
    Transición: IN_PROGRESS → COMPLETED (finaliza el torneo).

    Solo el creador puede completar la competición.
    """
    competition_id: UUID = Field(..., description=COMPETITION_ID_DESC)


class CompleteCompetitionResponseDTO(BaseModel):
    """
    DTO de salida para completar competición.
    """
    id: UUID = Field(..., description=COMPETITION_ID_DESC)
    status: str = Field(..., description="Nuevo estado (COMPLETED).")
    completed_at: datetime = Field(..., description="Fecha y hora de finalización.")

    model_config = ConfigDict(from_attributes=True)


# ======================================================================================
# DTOs para Delete y Cancel Competition
# ======================================================================================

# --------------------------------------------------------------------------------------
# Delete Competition (eliminación física - solo DRAFT)
# --------------------------------------------------------------------------------------

class DeleteCompetitionRequestDTO(BaseModel):
    """
    DTO de entrada para eliminar físicamente una competición.

    Restricciones:
    - Solo se puede eliminar en estado DRAFT (antes de activar)
    - Solo el creador puede eliminar
    - Se elimina permanentemente de la BD (incluyendo enrollments)
    """
    competition_id: UUID = Field(..., description=COMPETITION_ID_DESC)


class DeleteCompetitionResponseDTO(BaseModel):
    """
    DTO de salida para eliminación de competición.
    """
    id: UUID = Field(..., description=COMPETITION_ID_DESC)
    name: str = Field(..., description=COMPETITION_NAME_DESC)
    deleted: bool = Field(default=True, description="Confirmación de eliminación.")
    deleted_at: datetime = Field(..., description="Fecha y hora de eliminación.")

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------------------
# Cancel Competition (cancelación lógica - cualquier estado no final)
# --------------------------------------------------------------------------------------

class CancelCompetitionRequestDTO(BaseModel):
    """
    DTO de entrada para cancelar una competición.
    Transición: cualquier estado → CANCELLED (cancelación lógica).

    Restricciones:
    - No se puede cancelar si ya está en estado final (COMPLETED/CANCELLED)
    - Solo el creador puede cancelar
    - Se mantiene el registro histórico (no se elimina)

    Use cases:
    - Cancelar por mal tiempo
    - Cancelar por falta de participantes
    - Cancelar por razones organizativas
    """
    competition_id: UUID = Field(..., description=COMPETITION_ID_DESC)
    reason: str | None = Field(
        None,
        max_length=500,
        description="Razón de la cancelación (opcional)."
    )


class CancelCompetitionResponseDTO(BaseModel):
    """
    DTO de salida para cancelación de competición.
    """
    id: UUID = Field(..., description=COMPETITION_ID_DESC)
    status: str = Field(..., description="Nuevo estado (CANCELLED).")
    reason: str | None = Field(None, description="Razón de la cancelación.")
    cancelled_at: datetime = Field(..., description="Fecha y hora de cancelación.")

    model_config = ConfigDict(from_attributes=True)
