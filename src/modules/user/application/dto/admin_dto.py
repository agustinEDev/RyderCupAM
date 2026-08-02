"""DTOs para el panel de administración (gestión de usuarios y estadísticas)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class AdminListUsersRequestDTO(BaseModel):
    """DTO de entrada para listar usuarios (admin)."""

    search: str | None = Field(
        default=None, description="Filtro por nombre, apellidos o email (opcional)."
    )
    is_admin: bool | None = Field(
        default=None, description="Filtra por rol: True=admins, False=jugadores."
    )
    is_active: bool | None = Field(
        default=None, description="Filtra por estado: True=activas, False=desactivadas."
    )
    email_verified: bool | None = Field(
        default=None, description="Filtra por verificación de email."
    )
    limit: int = Field(default=20, ge=1, le=100, description="Tamaño de página.")
    offset: int = Field(default=0, ge=0, description="Desplazamiento de paginación.")


class AdminUserSummaryDTO(BaseModel):
    """Fila de la tabla de usuarios del panel de administración."""

    id: UUID
    first_name: str
    last_name: str
    email: EmailStr
    handicap: float | None = None
    is_admin: bool
    is_active: bool
    email_verified: bool
    created_at: datetime


class AdminListUsersResponseDTO(BaseModel):
    """Respuesta paginada del listado de usuarios."""

    users: list[AdminUserSummaryDTO]
    total_count: int
    limit: int
    offset: int


class AdminUpdateUserRequestDTO(BaseModel):
    """
    DTO de entrada para editar un usuario desde el panel de administración.

    Todos los campos son opcionales: solo se actualizan los que vengan informados.
    """

    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    handicap: float | None = None
    country_code: str | None = None
    is_admin: bool | None = None


class AdminSetUserActiveRequestDTO(BaseModel):
    """DTO de entrada para (des)activar una cuenta."""

    is_active: bool = Field(..., description="True para reactivar, False para desactivar.")


class AdminStatsResponseDTO(BaseModel):
    """Estadísticas globales de la plataforma para el panel de administración."""

    total_users: int
    total_competitions: int
    total_quick_matches: int
    total_golf_courses_approved: int
    total_golf_courses_pending: int
