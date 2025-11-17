# -*- coding: utf-8 -*-
"""DTOs para el módulo Competition - Application Layer."""

from datetime import datetime, date
from typing import Optional, Dict
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ConfigDict
from decimal import Decimal


# ======================================================================================
# DTO para el Caso de Uso: Crear Competition
# ======================================================================================

class CreateCompetitionRequestDTO(BaseModel):
    """
    DTO de entrada para el caso de uso de creación de competición.
    Define los datos necesarios para crear un nuevo torneo.
    """
    name: str = Field(..., min_length=3, max_length=100, description="Nombre de la competición.")
    start_date: date = Field(..., description="Fecha de inicio del torneo.")
    end_date: date = Field(..., description="Fecha de fin del torneo.")

    # Location
    main_country: str = Field(..., min_length=2, max_length=2, description="Código ISO del país principal (ej: 'ES').")
    adjacent_country_1: Optional[str] = Field(None, min_length=2, max_length=2, description="Código ISO del país adyacente 1 (opcional).")
    adjacent_country_2: Optional[str] = Field(None, min_length=2, max_length=2, description="Código ISO del país adyacente 2 (opcional).")

    # Handicap Settings
    handicap_type: str = Field(..., description="Tipo de hándicap: 'SCRATCH' o 'PERCENTAGE'.")
    handicap_percentage: Optional[int] = Field(None, ge=90, le=100, description="Porcentaje de hándicap (90, 95 o 100). Requerido si type='PERCENTAGE'.")

    # Competition Config
    max_players: int = Field(default=24, ge=2, le=100, description="Número máximo de jugadores.")
    team_assignment: str = Field(default="MANUAL", description="Asignación de equipos: 'MANUAL' o 'AUTOMATIC'.")

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

    def model_post_init(self, __context) -> None:
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


class CreateCompetitionResponseDTO(BaseModel):
    """
    DTO de salida para el caso de uso de creación de competición.
    Devuelve los datos básicos de la competición creada.
    """
    id: UUID = Field(..., description="ID único de la competición.")
    creator_id: UUID = Field(..., description="ID del usuario creador.")
    name: str = Field(..., description="Nombre de la competición.")
    status: str = Field(..., description="Estado de la competición (DRAFT al crear).")
    start_date: date = Field(..., description="Fecha de inicio.")
    end_date: date = Field(..., description="Fecha de fin.")
    created_at: datetime = Field(..., description="Fecha y hora de creación.")

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
    name: Optional[str] = Field(None, min_length=3, max_length=100, description="Nuevo nombre de la competición.")
    start_date: Optional[date] = Field(None, description="Nueva fecha de inicio.")
    end_date: Optional[date] = Field(None, description="Nueva fecha de fin.")

    # Location
    main_country: Optional[str] = Field(None, min_length=2, max_length=2, description="Nuevo país principal.")
    adjacent_country_1: Optional[str] = Field(None, min_length=2, max_length=2, description="Nuevo país adyacente 1.")
    adjacent_country_2: Optional[str] = Field(None, min_length=2, max_length=2, description="Nuevo país adyacente 2.")

    # Handicap Settings
    handicap_type: Optional[str] = Field(None, description="Nuevo tipo de hándicap.")
    handicap_percentage: Optional[int] = Field(None, ge=90, le=100, description="Nuevo porcentaje de hándicap.")

    # Competition Config
    max_players: Optional[int] = Field(None, ge=2, le=100, description="Nuevo máximo de jugadores.")
    team_assignment: Optional[str] = Field(None, description="Nueva asignación de equipos.")

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
    id: UUID = Field(..., description="ID de la competición actualizada.")
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
    """
    id: UUID = Field(..., description="ID único de la competición.")
    creator_id: UUID = Field(..., description="ID del usuario creador.")
    name: str = Field(..., description="Nombre de la competición.")
    status: str = Field(..., description="Estado actual (DRAFT, ACTIVE, CLOSED, etc.).")

    # Dates
    start_date: date = Field(..., description="Fecha de inicio.")
    end_date: date = Field(..., description="Fecha de fin.")

    # Location (serializado como dict)
    location: Dict[str, Optional[str]] = Field(..., description="Ubicación con países.")

    # Handicap Settings (serializado como dict)
    handicap_settings: Dict[str, Optional[int]] = Field(..., description="Configuración de hándicaps.")

    # Config
    max_players: int = Field(..., description="Número máximo de jugadores.")
    team_assignment: str = Field(..., description="Tipo de asignación de equipos.")

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
