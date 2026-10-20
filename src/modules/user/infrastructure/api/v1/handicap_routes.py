"""
Handicap API Routes - Infrastructure Layer

Endpoints HTTP para gestión de hándicaps de usuarios.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from src.config.dependencies import (
    get_current_user,
    get_refresh_own_handicap_use_case,
    get_update_handicap_manually_use_case,
    get_update_handicap_use_case,
    get_update_multiple_handicaps_use_case,
)
from src.config.rate_limit import limiter
from src.modules.user.application.dto.user_dto import (
    RefreshOwnHandicapRequestDTO,
    RefreshOwnHandicapResponseDTO,
    UserResponseDTO,
)
from src.modules.user.application.use_cases.refresh_own_handicap_use_case import (
    RefreshOwnHandicapUseCase,
)
from src.modules.user.application.use_cases.update_multiple_handicaps_use_case import (
    UpdateMultipleHandicapsUseCase,
)
from src.modules.user.application.use_cases.update_user_handicap_manually_use_case import (
    UpdateUserHandicapManuallyUseCase,
)
from src.modules.user.application.use_cases.update_user_handicap_use_case import (
    UpdateUserHandicapUseCase,
)
from src.modules.user.domain.errors.handicap_errors import (
    HandicapNotFoundError,
    HandicapServiceUnavailableError,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.security.authorization import (
    require_admin,
    require_self_or_admin,
)

router = APIRouter(prefix="/handicaps")


# === Request/Response DTOs ===


class UpdateHandicapRequestDTO(BaseModel):
    """DTO para solicitud de actualización de hándicap individual."""

    user_id: UUID
    manual_handicap: float | None = Field(
        None,
        ge=-10.0,
        le=54.0,
        description="Hándicap manual (opcional). Solo se usa si no se encuentra en RFEG.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "manual_handicap": 15.5,
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
        description="Nuevo valor del hándicap (debe estar entre -10.0 y 54.0)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "handicap": 15.5,
            }
        }
    )


class UpdateMultipleHandicapsRequestDTO(BaseModel):
    """DTO para solicitud de actualización de múltiples hándicaps."""

    user_ids: list[UUID]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_ids": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "123e4567-e89b-12d3-a456-426614174001",
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
                "message": "Procesados 10 usuarios: 7 actualizados, 1 no encontrado, 1 sin hándicap, 1 error",
            }
        }
    )


# === Endpoints ===


@router.post(
    "/refresh-mine",
    response_model=RefreshOwnHandicapResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Refrescar mi hándicap desde la RFEG",
    description=(
        "Refresca desde la RFEG el hándicap del usuario autenticado, una vez al día "
        "y solo si es español, y dice si hay que pedírselo (needs_handicap). "
        "Sustituye al refresco que hacía el login, que esperaba a la RFEG antes de "
        "contestar (RyderCupAM#340)."
    ),
)
@limiter.limit("10/hour")  # Por usuario (#273): cada vez puede esperar a la RFEG
async def refresh_own_handicap(
    request: Request,  # noqa: ARG001 - Requerido por SlowAPI limiter
    use_case: RefreshOwnHandicapUseCase = Depends(get_refresh_own_handicap_use_case),
    current_user: UserResponseDTO = Depends(get_current_user),
) -> RefreshOwnHandicapResponseDTO:
    """
    Refresca el hándicap del usuario autenticado.

    Lo acotan la regla de una vez al día (tras un refresco correcto no se vuelve
    a preguntar a la RFEG hasta mañana) y un límite de 10/hora por usuario, que
    frena a quien la RFEG no encuentra: a él se le pregunta en cada llamada, y
    cada una puede esperar hasta 10 s. El frontend la llama una vez por login
    (#273; antes no tenía límite porque todo el tráfico compartía uno, ADR-038).

    Raises:
        404: Si el usuario autenticado ya no existe
    """
    result = await use_case.execute(RefreshOwnHandicapRequestDTO(user_id=current_user.id))
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    return result


@router.post(
    "/update",
    response_model=UserResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar hándicap de un usuario",
    description=(
        "Busca y actualiza el hándicap de un usuario consultando la RFEG. "
        "Si el usuario no tiene hándicap registrado en la RFEG y se proporciona "
        "manual_handicap, se usará ese valor. "
        "Cada jugador solo puede actualizar el suyo; un administrador, el de cualquiera."
    ),
)
@limiter.limit("5/hour")  # Proteger RFEG API externa: 5 consultas por hora y usuario
async def update_user_handicap(
    request: Request,  # noqa: ARG001 - Requerido por SlowAPI limiter
    handicap_data: UpdateHandicapRequestDTO,
    use_case: UpdateUserHandicapUseCase = Depends(get_update_handicap_use_case),
    current_user: UserResponseDTO = Depends(get_current_user),
):
    """
    Actualiza el hándicap de un usuario buscándolo en la RFEG.

    Args:
        request: DTO con el ID del usuario y opcionalmente hándicap manual
        use_case: Caso de uso inyectado por FastAPI

    Returns:
        Usuario actualizado con su hándicap

    Raises:
        403: Si no es el propio usuario ni un admin
        404: Si el usuario no existe o no se encuentra su hándicap en RFEG
        503: Si el servicio RFEG no está disponible
    """
    require_self_or_admin(current_user, handicap_data.user_id)

    try:
        user_id = UserId(handicap_data.user_id)
        result = await use_case.execute(user_id, handicap_data.manual_handicap)

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {handicap_data.user_id} no encontrado",
            )

        return result

    except HandicapNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
    except HandicapServiceUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"El servicio de hándicap no está disponible: {e!s}",
        ) from None


@router.post(
    "/update-multiple",
    response_model=UpdateMultipleHandicapsResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar hándicaps de múltiples usuarios",
    description=(
        "Actualiza los hándicaps de una lista de usuarios. "
        "Útil para actualizar todos los participantes de una competición antes de iniciarla. "
        "Solo administradores."
    ),
)
async def update_multiple_handicaps(
    request: UpdateMultipleHandicapsRequestDTO,
    use_case: UpdateMultipleHandicapsUseCase = Depends(get_update_multiple_handicaps_use_case),
    current_user: UserResponseDTO = Depends(get_current_user),
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

    Raises:
        403: Si no es un admin
    """
    require_admin(current_user)

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

    return UpdateMultipleHandicapsResponseDTO(**stats, message=message)


@router.post(
    "/update-manual",
    response_model=UserResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar hándicap manualmente",
    description=(
        "Actualiza el hándicap de un usuario con un valor manual proporcionado. "
        "Este endpoint NO consulta la RFEG, actualiza directamente con el valor dado. "
        "Útil para jugadores no federados. "
        "Cada jugador solo puede cambiar el suyo; un administrador, el de cualquiera."
    ),
)
async def update_user_handicap_manually(
    request: UpdateHandicapManuallyRequestDTO,
    use_case: UpdateUserHandicapManuallyUseCase = Depends(get_update_handicap_manually_use_case),
    current_user: UserResponseDTO = Depends(get_current_user),
):
    """
    Actualiza el hándicap de un usuario manualmente (sin consultar RFEG).

    Args:
        request: DTO con el ID del usuario y el nuevo valor de hándicap
        use_case: Caso de uso inyectado por FastAPI con gestión automática de sesiones

    Returns:
        Usuario actualizado con su nuevo hándicap

    Raises:
        403: Si no es el propio usuario ni un admin
        404: Si el usuario no existe
        400: Si el hándicap no está en el rango válido
    """
    require_self_or_admin(current_user, request.user_id)

    user_id = UserId(request.user_id)

    try:
        result = await use_case.execute(user_id, request.handicap)

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {request.user_id} no encontrado",
            )

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
