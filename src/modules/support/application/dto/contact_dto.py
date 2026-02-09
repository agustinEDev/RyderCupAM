"""
Contact DTOs - Application Layer

DTOs para el formulario de contacto/soporte.
"""

from pydantic import BaseModel, EmailStr, Field

from src.modules.support.domain.value_objects.contact_category import ContactCategory


class ContactRequestDTO(BaseModel):
    """DTO para la solicitud de contacto."""

    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    category: ContactCategory
    subject: str = Field(..., min_length=3, max_length=200)
    message: str = Field(..., min_length=10, max_length=5000)


class ContactResponseDTO(BaseModel):
    """DTO para la respuesta del formulario de contacto."""

    message: str
