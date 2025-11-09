"""
Handicap API Routes - Infrastructure Layer

Endpoints HTTP para gestión de hándicaps de usuarios.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from uuid import UUID

from src.modules.user.application.use_cases.update_user_handicap_use_case import UpdateUserHandicapUseCase
from src.modules.user.application.use_cases.update_multiple_handicaps_use_case import UpdateMultipleHandicapsUseCase
from src.modules.user.application.use_cases.update_user_handicap_manually_use_case import UpdateUserHandicapManuallyUseCase
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.value_objects.user_id import UserId
from src.config.dependencies import get_update_handicap_use_case, get_update_multiple_handicaps_use_case, get_update_handicap_manually_use_case


router = APIRouter(prefix="/handicaps", tags=["handicaps"])


# === Request/Response DTOs ===

class UpdateHandicapRequestDTO(BaseModel):
    """DTO para solicitud de actualización de hándicap individual."""
    user_id: UUID
    manual_handicap: Optional[float] = Field(
        None,
        ge=-10.0,
        le=54.0,
        description="Hándicap manual (opcional). Solo se usa si no se encuentra en RFEG."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "manual_handicap": 15.5
            }
        }
    )


class UpdateHandicapManuallyRequestDTO(BaseModel):
    """DTO para solicitud de actualización manual de hándicap."""
    user_id: UUID
    handicap: float = Field(
        ...,
        ge=-10.0,
        le=54.0,
        description="Nuevo valor del hándicap (debe estar entre -10.0 y 54.0)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "handicap": 15.5
            }
        }
    )


class UpdateMultipleHandicapsRequestDTO(BaseModel):
    """DTO para solicitud de actualización de múltiples hándicaps."""
    user_ids: List[UUID]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_ids": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "123e4567-e89b-12d3-a456-426614174001"
                ]
            }
        }
    )


class UpdateMultipleHandicapsResponseDTO(BaseModel):
    """DTO para respuesta de actualización múltiple."""
    total: int
    updated: int
    not_found: int
    no_handicap_found: int
    errors: int
    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 10,
                "updated": 7,
                "not_found": 1,
                "no_handicap_found": 1,
                "errors": 1,
                "message": "Procesados 10 usuarios: 7 actualizados, 1 no encontrado, 1 sin hándicap, 1 error"
            }
        }
    )


# === Endpoints ===

@router.post(
    "/update",
    response_model=UserResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar hándicap de un usuario",
    description=(
        "Busca y actualiza el hándicap de un usuario consultando la RFEG. "
        "Si el usuario no tiene hándicap registrado en la RFEG y se proporciona "
        "manual_handicap, se usará ese valor."
    )
)
async def update_user_handicap(
    request: UpdateHandicapRequestDTO,
    use_case: UpdateUserHandicapUseCase = Depends(get_update_handicap_use_case)
):
    """
    Actualiza el hándicap de un usuario buscándolo en la RFEG.

    Args:
        request: DTO con el ID del usuario y opcionalmente hándicap manual
        use_case: Caso de uso inyectado por FastAPI

    Returns:
        Usuario actualizado con su hándicap

    Raises:
        404: Si el usuario no existe
    """
    user_id = UserId(request.user_id)
    result = await use_case.execute(user_id, request.manual_handicap)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {request.user_id} no encontrado"
        )

    return result


@router.post(
    "/update-multiple",
    response_model=UpdateMultipleHandicapsResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar hándicaps de múltiples usuarios",
    description=(
        "Actualiza los hándicaps de una lista de usuarios. "
        "Útil para actualizar todos los participantes de una competición antes de iniciarla."
    )
)
async def update_multiple_handicaps(
    request: UpdateMultipleHandicapsRequestDTO,
    use_case: UpdateMultipleHandicapsUseCase = Depends(get_update_multiple_handicaps_use_case)
):
    """
    Actualiza los hándicaps de múltiples usuarios.

    Este endpoint es útil para:
    - Actualizar participantes de una competición
    - Actualizar jugadores de un partido
    - Actualizaciones masivas programadas

    Args:
        request: DTO con la lista de IDs de usuarios
        use_case: Caso de uso inyectado por FastAPI

    Returns:
        Estadísticas de la operación (total, actualizados, errores, etc.)
    """
    user_ids = [UserId(uid) for uid in request.user_ids]
    stats = await use_case.execute(user_ids)

    # Construir mensaje descriptivo
    message = (
        f"Procesados {stats['total']} usuarios: "
        f"{stats['updated']} actualizados, "
        f"{stats['not_found']} no encontrados, "
        f"{stats['no_handicap_found']} sin hándicap, "
        f"{stats['errors']} errores"
    )

    return UpdateMultipleHandicapsResponseDTO(
        **stats,
        message=message
    )


@router.post(
    "/update-manual",
    response_model=UserResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar hándicap manualmente",
    description=(
        "Actualiza el hándicap de un usuario con un valor manual proporcionado. "
        "Este endpoint NO consulta la RFEG, actualiza directamente con el valor dado. "
        "Útil para administradores o para jugadores no federados."
    )
)
async def update_user_handicap_manually(
    request: UpdateHandicapManuallyRequestDTO,
    use_case: UpdateUserHandicapManuallyUseCase = Depends(get_update_handicap_manually_use_case)
):
    """
    Actualiza el hándicap de un usuario manualmente (sin consultar RFEG).

    Args:
        request: DTO con el ID del usuario y el nuevo valor de hándicap
        use_case: Caso de uso inyectado por FastAPI con gestión automática de sesiones

    Returns:
        Usuario actualizado con su nuevo hándicap

    Raises:
        404: Si el usuario no existe
        400: Si el hándicap no está en el rango válido
    """
    user_id = UserId(request.user_id)

    try:
        result = await use_case.execute(user_id, request.handicap)

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {request.user_id} no encontrado"
            )

        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
