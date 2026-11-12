"""
Country Routes - API REST Layer (Shared Infrastructure).

Endpoints FastAPI para consultar países y sus adyacencias.
Endpoints de solo lectura (seed data).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.config.dependencies import get_country_repository
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.domain.value_objects.country_code import CountryCode

router = APIRouter()


# ======================================================================================
# DTOs para Countries (Presentation Layer)
# ======================================================================================


class CountryResponseDTO(BaseModel):
    """DTO de respuesta para un país."""

    code: str = Field(..., description="Código ISO 3166-1 alpha-2 del país")
    name_en: str = Field(..., description="Nombre en inglés")
    name_es: str = Field(..., description="Nombre en español")

    class Config:
        from_attributes = True


# ======================================================================================
# ENDPOINTS
# ======================================================================================


@router.get(
    "",
    response_model=list[CountryResponseDTO],
    summary="Listar países activos",
    description="Obtiene todos los países activos para poblar selectores en el frontend.",
)
async def list_countries(
    paises: CountryRepositoryInterface = Depends(get_country_repository),
) -> list[CountryResponseDTO]:
    """
    Lista todos los países activos.

    Útil para poblar el selector de país principal en el formulario de creación
    de competiciones.
    """
    countries = await paises.find_all_active()

    return [
        CountryResponseDTO(
            code=(str(country.code.value) if hasattr(country.code, "value") else str(country.code)),
            name_en=country.name_en,
            name_es=country.name_es,
        )
        for country in countries
    ]


@router.get(
    "/{country_code}/adjacent",
    response_model=list[CountryResponseDTO],
    summary="Listar países adyacentes",
    description="Obtiene los países que comparten frontera con el país especificado.",
)
async def list_adjacent_countries(
    country_code: str,
    paises: CountryRepositoryInterface = Depends(get_country_repository),
) -> list[CountryResponseDTO]:
    """
    Lista los países adyacentes a un país dado.

    Útil para poblar los selectores de país secundario y terciario
    en el formulario de creación de competiciones.

    Args:
        country_code: Código ISO del país (ej: "ES", "FR")

    Returns:
        Lista de países adyacentes ordenados alfabéticamente

    Raises:
        404: Si el país no existe
    """
    # Validar que el país existe
    try:
        code = CountryCode(country_code.upper())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Código de país inválido: {country_code}",
        ) from e

    country = await paises.find_by_code(code)
    if not country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"País no encontrado: {country_code}",
        )

    # Obtener países adyacentes
    adjacent = await paises.find_adjacent_countries(code)

    return [
        CountryResponseDTO(
            code=str(c.code.value) if hasattr(c.code, "value") else str(c.code),
            name_en=c.name_en,
            name_es=c.name_es,
        )
        for c in adjacent
    ]
