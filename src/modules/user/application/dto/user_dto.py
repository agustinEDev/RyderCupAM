from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict


# ======================================================================================
# DTO para el Caso de Uso: Registrar Usuario
# ======================================================================================

class RegisterUserRequestDTO(BaseModel):
    """
    DTO de entrada para el caso de uso de registro de usuario.
    Define los datos necesarios para crear un nuevo usuario.
    """
    email: EmailStr = Field(..., description="Correo electrónico del usuario.")
    password: str = Field(..., min_length=8, description="Contraseña del usuario (mínimo 8 caracteres).")
    first_name: str = Field(..., min_length=2, description="Nombre del usuario.")
    last_name: str = Field(..., min_length=2, description="Apellido del usuario.")
    manual_handicap: Optional[float] = Field(
        None,
        ge=-10.0,
        le=54.0,
        description="Hándicap manual (opcional). Solo se usa si no se encuentra en RFEG."
    )

# ======================================================================================
# DTO para el Caso de Uso: Buscar Usuario
# ======================================================================================

class FindUserRequestDTO(BaseModel):
    """
    DTO de entrada para el caso de uso de búsqueda de usuario.
    Permite buscar por email o nombre completo.
    """
    email: Optional[EmailStr] = Field(None, description="Correo electrónico del usuario.")
    full_name: Optional[str] = Field(None, min_length=3, description="Nombre completo del usuario.")

    @field_validator('email', 'full_name', mode='before')
    @classmethod 
    def check_at_least_one_field(cls, v, info):
        """Valida que se proporcione al menos un campo de búsqueda."""
        return v

    def model_post_init(self, __context) -> None:
        """Valida que se proporcione al menos un criterio de búsqueda."""
        if not self.email and not self.full_name:
            raise ValueError("Debe proporcionar al menos 'email' o 'full_name' para la búsqueda.")

class FindUserResponseDTO(BaseModel):
    """
    DTO de respuesta para el caso de uso de búsqueda de usuario.
    Devuelve información básica del usuario encontrado.
    """
    user_id: UUID = Field(..., description="ID único del usuario encontrado.")
    email: EmailStr = Field(..., description="Correo electrónico del usuario.")
    full_name: str = Field(..., description="Nombre completo del usuario.")

    # Configuración de Pydantic actualizada para V2
    model_config = ConfigDict(from_attributes=True)

# ======================================================================================
# DTO de Respuesta Genérico para el Usuario
# ======================================================================================

class UserResponseDTO(BaseModel):
    """
    DTO de salida que representa a un usuario.
    Se utiliza para devolver información del usuario de forma segura (sin contraseña).
    """
    id: UUID = Field(..., description="ID único del usuario.")
    email: EmailStr = Field(..., description="Correo electrónico del usuario.")
    first_name: str = Field(..., description="Nombre del usuario.")
    last_name: str = Field(..., description="Apellido del usuario.")
    handicap: Optional[float] = Field(None, description="Handicap de golf del usuario.")
    created_at: datetime = Field(..., description="Fecha y hora de creación del usuario.")
    updated_at: datetime = Field(..., description="Fecha y hora de la última actualización.")

    # Configuración de Pydantic actualizada para V2
    model_config = ConfigDict(from_attributes=True)

    @field_validator("id", "email", mode="before")
    @classmethod
    def convert_value_objects(cls, v):
        """
        Convierte nuestros Value Objects a tipos primitivos que Pydantic entiende.
        Se ejecuta ANTES de la validación estándar de Pydantic.
        """
        # Si el valor 'v' tiene un atributo 'value', usamos ese valor.
        # Esto funciona para UserId y Email.
        if hasattr(v, "value"):
            return v.value
        return v