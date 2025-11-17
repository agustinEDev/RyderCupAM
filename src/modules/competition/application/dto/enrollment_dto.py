# -*- coding: utf-8 -*-
"""DTOs para Enrollment - Application Layer."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ConfigDict
from decimal import Decimal


# ======================================================================================
# DTO para el Caso de Uso: Solicitar Inscripción (Request Enrollment)
# ======================================================================================

class RequestEnrollmentRequestDTO(BaseModel):
    """
    DTO de entrada para que un jugador solicite inscribirse a una competición.
    """
    competition_id: UUID = Field(..., description="ID de la competición a la que se solicita inscripción.")
    user_id: UUID = Field(..., description="ID del usuario que solicita la inscripción.")


class RequestEnrollmentResponseDTO(BaseModel):
    """
    DTO de salida para solicitud de inscripción.
    """
    id: UUID = Field(..., description="ID único de la inscripción.")
    competition_id: UUID = Field(..., description="ID de la competición.")
    user_id: UUID = Field(..., description="ID del usuario.")
    status: str = Field(..., description="Estado de la inscripción (REQUESTED).")
    created_at: datetime = Field(..., description="Fecha y hora de la solicitud.")

    model_config = ConfigDict(from_attributes=True)


# ======================================================================================
# DTO para el Caso de Uso: Inscripción Directa por Creador
# ======================================================================================

class DirectEnrollPlayerRequestDTO(BaseModel):
    """
    DTO de entrada para que el creador inscriba directamente a un jugador.
    """
    competition_id: UUID = Field(..., description="ID de la competición.")
    user_id: UUID = Field(..., description="ID del jugador a inscribir.")
    custom_handicap: Optional[Decimal] = Field(
        None,
        ge=Decimal("-10.0"),
        le=Decimal("54.0"),
        description="Hándicap personalizado (opcional). Override del hándicap oficial."
    )


class DirectEnrollPlayerResponseDTO(BaseModel):
    """
    DTO de salida para inscripción directa.
    """
    id: UUID = Field(..., description="ID único de la inscripción.")
    competition_id: UUID = Field(..., description="ID de la competición.")
    user_id: UUID = Field(..., description="ID del jugador.")
    status: str = Field(..., description="Estado de la inscripción (APPROVED).")
    custom_handicap: Optional[Decimal] = Field(None, description="Hándicap personalizado si se especificó.")
    created_at: datetime = Field(..., description="Fecha y hora de la inscripción.")

    model_config = ConfigDict(from_attributes=True)


# ======================================================================================
# DTO para el Caso de Uso: Manejar Solicitud de Inscripción (Approve/Reject)
# ======================================================================================

class HandleEnrollmentRequestDTO(BaseModel):
    """
    DTO de entrada para que el creador apruebe o rechace una solicitud.
    """
    enrollment_id: UUID = Field(..., description="ID de la inscripción a procesar.")
    action: str = Field(..., description="Acción a realizar: 'APPROVE' o 'REJECT'.")

    @field_validator('action', mode='before')
    @classmethod
    def uppercase_action(cls, v):
        """Convierte action a mayúsculas."""
        if v:
            return v.upper().strip()
        return v

    def model_post_init(self, __context) -> None:
        """Validar que action sea válida."""
        if self.action not in ["APPROVE", "REJECT"]:
            raise ValueError("action debe ser 'APPROVE' o 'REJECT'")


class HandleEnrollmentResponseDTO(BaseModel):
    """
    DTO de salida para manejar solicitud de inscripción.
    """
    id: UUID = Field(..., description="ID de la inscripción.")
    competition_id: UUID = Field(..., description="ID de la competición.")
    user_id: UUID = Field(..., description="ID del usuario.")
    status: str = Field(..., description="Nuevo estado (APPROVED o REJECTED).")
    updated_at: datetime = Field(..., description="Fecha y hora de actualización.")

    model_config = ConfigDict(from_attributes=True)


# ======================================================================================
# DTO para el Caso de Uso: Cancelar Inscripción (Player Cancels)
# ======================================================================================

class CancelEnrollmentRequestDTO(BaseModel):
    """
    DTO de entrada para que un jugador cancele su solicitud o decline invitación.
    """
    enrollment_id: UUID = Field(..., description="ID de la inscripción a cancelar.")
    reason: Optional[str] = Field(None, max_length=500, description="Razón de la cancelación (opcional).")


class CancelEnrollmentResponseDTO(BaseModel):
    """
    DTO de salida para cancelación de inscripción.
    """
    id: UUID = Field(..., description="ID de la inscripción.")
    competition_id: UUID = Field(..., description="ID de la competición.")
    user_id: UUID = Field(..., description="ID del usuario.")
    status: str = Field(..., description="Estado (CANCELLED).")
    updated_at: datetime = Field(..., description="Fecha y hora de cancelación.")

    model_config = ConfigDict(from_attributes=True)


# ======================================================================================
# DTO para el Caso de Uso: Retirar Inscripción (Player Withdraws)
# ======================================================================================

class WithdrawEnrollmentRequestDTO(BaseModel):
    """
    DTO de entrada para que un jugador se retire después de estar aprobado.
    """
    enrollment_id: UUID = Field(..., description="ID de la inscripción a retirar.")
    reason: Optional[str] = Field(None, max_length=500, description="Razón del retiro (opcional).")


class WithdrawEnrollmentResponseDTO(BaseModel):
    """
    DTO de salida para retiro de inscripción.
    """
    id: UUID = Field(..., description="ID de la inscripción.")
    competition_id: UUID = Field(..., description="ID de la competición.")
    user_id: UUID = Field(..., description="ID del usuario.")
    status: str = Field(..., description="Estado (WITHDRAWN).")
    updated_at: datetime = Field(..., description="Fecha y hora de retiro.")

    model_config = ConfigDict(from_attributes=True)


# ======================================================================================
# DTO para el Caso de Uso: Establecer Hándicap Personalizado
# ======================================================================================

class SetCustomHandicapRequestDTO(BaseModel):
    """
    DTO de entrada para que el creador establezca un hándicap personalizado.
    """
    enrollment_id: UUID = Field(..., description="ID de la inscripción.")
    custom_handicap: Decimal = Field(
        ...,
        ge=Decimal("-10.0"),
        le=Decimal("54.0"),
        description="Hándicap personalizado (override del oficial)."
    )


class SetCustomHandicapResponseDTO(BaseModel):
    """
    DTO de salida para establecer hándicap personalizado.
    """
    id: UUID = Field(..., description="ID de la inscripción.")
    custom_handicap: Decimal = Field(..., description="Nuevo hándicap personalizado.")
    updated_at: datetime = Field(..., description="Fecha y hora de actualización.")

    model_config = ConfigDict(from_attributes=True)


# ======================================================================================
# DTO de Respuesta Genérico para Enrollment
# ======================================================================================

class EnrollmentResponseDTO(BaseModel):
    """
    DTO de salida genérico para representar una inscripción.
    Se utiliza para listar inscripciones y consultas detalladas.
    """
    id: UUID = Field(..., description="ID único de la inscripción.")
    competition_id: UUID = Field(..., description="ID de la competición.")
    user_id: UUID = Field(..., description="ID del usuario.")
    status: str = Field(..., description="Estado actual (REQUESTED, APPROVED, etc.).")
    team_id: Optional[str] = Field(None, description="ID del equipo asignado (si aplica).")
    custom_handicap: Optional[Decimal] = Field(None, description="Hándicap personalizado (si aplica).")
    created_at: datetime = Field(..., description="Fecha y hora de creación.")
    updated_at: datetime = Field(..., description="Fecha y hora de última actualización.")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("id", "competition_id", "user_id", mode="before")
    @classmethod
    def convert_value_objects_uuid(cls, v):
        """Convierte Value Objects UUID a UUID primitivo."""
        if hasattr(v, "value"):
            return v.value
        return v

    @field_validator("status", mode="before")
    @classmethod
    def convert_enrollment_status(cls, v):
        """Convierte EnrollmentStatus enum a string."""
        if hasattr(v, "value"):
            return v.value
        return v
