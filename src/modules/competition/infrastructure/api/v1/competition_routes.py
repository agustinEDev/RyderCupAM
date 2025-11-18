# -*- coding: utf-8 -*-
"""
Competition Routes - API REST Layer (Infrastructure).

Endpoints FastAPI para el módulo Competition siguiendo Clean Architecture.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from uuid import UUID

from src.config.dependencies import (
    get_current_user,
    get_competition_uow,
    get_create_competition_use_case,
    get_list_competitions_use_case,
    get_get_competition_use_case,
    get_update_competition_use_case,
    get_delete_competition_use_case,
    get_activate_competition_use_case,
    get_close_enrollments_use_case,
    get_start_competition_use_case,
    get_complete_competition_use_case,
    get_cancel_competition_use_case,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    CreateCompetitionResponseDTO,
    UpdateCompetitionRequestDTO,
    CompetitionResponseDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
    CompetitionAlreadyExistsError,
)
from src.modules.competition.application.use_cases.list_competitions_use_case import (
    ListCompetitionsUseCase,
)
from src.modules.competition.application.use_cases.get_competition_use_case import (
    GetCompetitionUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    UpdateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.delete_competition_use_case import (
    DeleteCompetitionUseCase,
)
from src.modules.competition.application.use_cases.activate_competition_use_case import (
    ActivateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.start_competition_use_case import (
    StartCompetitionUseCase,
)
from src.modules.competition.application.use_cases.complete_competition_use_case import (
    CompleteCompetitionUseCase,
)
from src.modules.competition.application.use_cases.cancel_competition_use_case import (
    CancelCompetitionUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.competition.domain.value_objects.competition_id import CompetitionId

logger = logging.getLogger(__name__)
router = APIRouter()


# ======================================================================================
# HELPER: CompetitionDTOMapper (Presentation Layer Logic)
# ======================================================================================

class CompetitionDTOMapper:
    """
    Mapper para convertir entidades Competition a DTOs de presentación.

    RESPONSABILIDAD: Capa de presentación (API Layer)
    - Convertir entidades de dominio a DTOs
    - Calcular campos derivados para UI (is_creator, enrolled_count, location)
    - Formatear datos para el frontend

    NO es responsabilidad del domain ni del application layer.
    """

    @staticmethod
    async def to_response_dto(
        competition: Competition,
        current_user_id: UserId,
        uow: CompetitionUnitOfWorkInterface,
    ) -> CompetitionResponseDTO:
        """
        Convierte una entidad Competition a CompetitionResponseDTO.

        Calcula campos dinámicos:
        - is_creator: si el usuario actual es el creador
        - enrolled_count: número de enrollments APPROVED
        - location: string formateado con nombres de países

        Args:
            competition: Entidad de dominio
            current_user_id: ID del usuario autenticado
            uow: Unit of Work para consultas adicionales (enrollments, countries)

        Returns:
            CompetitionResponseDTO enriquecido
        """
        # Calcular enrolled_count
        enrolled_count = await uow.enrollments.count_approved(competition.id)

        # Formatear location
        location_str = await CompetitionDTOMapper._format_location(competition, uow)

        # Construir DTO
        return CompetitionResponseDTO(
            id=competition.id.value,
            creator_id=competition.creator_id.value,
            name=str(competition.name),
            status=competition.status.value,
            # Dates
            start_date=competition.dates.start_date,
            end_date=competition.dates.end_date,
            # Location - raw codes
            country_code=competition.location.main_country.value,
            secondary_country_code=(
                competition.location.adjacent_country_1.value
                if competition.location.adjacent_country_1
                else None
            ),
            tertiary_country_code=(
                competition.location.adjacent_country_2.value
                if competition.location.adjacent_country_2
                else None
            ),
            # Location - formatted
            location=location_str,
            # Handicap
            handicap_type=competition.handicap_settings.type.value,
            handicap_percentage=competition.handicap_settings.percentage,
            # Config
            max_players=competition.max_players,
            team_assignment=competition.team_assignment.value,
            # Campos calculados
            is_creator=(competition.creator_id == current_user_id),
            enrolled_count=enrolled_count,
            # Timestamps
            created_at=competition.created_at,
            updated_at=competition.updated_at,
        )

    @staticmethod
    async def _format_location(
        competition: Competition,
        uow: CompetitionUnitOfWorkInterface,
    ) -> str:
        """
        Formatea la ubicación como string legible.

        Ejemplos:
        - Solo main: "Spain"
        - Main + 1: "Spain, France"
        - Main + 2: "Spain, France, Italy"

        Args:
            competition: Entidad Competition
            uow: Unit of Work para consultar nombres de países

        Returns:
            String formateado
        """
        location = competition.location
        country_names = []

        # País principal
        main_country = await uow.countries.find_by_code(location.main_country)
        if main_country:
            country_names.append(main_country.name_en)

        # País adyacente 1
        if location.adjacent_country_1:
            country = await uow.countries.find_by_code(location.adjacent_country_1)
            if country:
                country_names.append(country.name_en)

        # País adyacente 2
        if location.adjacent_country_2:
            country = await uow.countries.find_by_code(location.adjacent_country_2)
            if country:
                country_names.append(country.name_en)

        return ", ".join(country_names) if country_names else "Unknown"


# ======================================================================================
# CRUD ENDPOINTS
# ======================================================================================

@router.post(
    "",
    response_model=CreateCompetitionResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva competición",
    description="Crea una nueva competición en estado DRAFT. Requiere autenticación.",
    tags=["Competitions"],
)
async def create_competition(
    request: CreateCompetitionRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CreateCompetitionUseCase = Depends(get_create_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
):
    """
    Endpoint para crear una nueva competición.

    **Reglas de negocio:**
    - Cualquier usuario autenticado puede crear una competición
    - La competición se crea en estado DRAFT
    - El nombre debe ser único para el creador
    - Los países deben ser adyacentes (validado por domain service)

    **Request Body:**
    - name: Nombre de la competición (3-100 caracteres)
    - start_date: Fecha de inicio (futuro)
    - end_date: Fecha de fin (>= start_date)
    - main_country: Código ISO del país principal (ej: "ES")
    - adjacent_country_1/2: Países adyacentes opcionales
    - handicap_type: "SCRATCH" o "PERCENTAGE"
    - handicap_percentage: 90-100 (si type=PERCENTAGE)
    - max_players: Máximo de jugadores (default: 24)
    - team_assignment: "MANUAL" o "AUTOMATIC"

    **Returns:**
    - Competición creada con status=DRAFT
    - Campos calculados: is_creator=True, enrolled_count=0
    """
    try:
        creator_id = UserId(str(current_user.id))

        # Ejecutar use case (retorna DTO simple)
        response = await use_case.execute(request, creator_id)

        # Obtener la entidad completa para enriquecer el response
        async with uow:
            competition = await uow.competitions.find_by_id(
                CompetitionId(response.id)
            )

            if not competition:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Competition created but not found",
                )

            # Convertir a DTO enriquecido
            enriched_dto = await CompetitionDTOMapper.to_response_dto(
                competition, creator_id, uow
            )

            # Construir CreateCompetitionResponseDTO con todos los campos
            return CreateCompetitionResponseDTO(
                id=enriched_dto.id,
                creator_id=enriched_dto.creator_id,
                name=enriched_dto.name,
                status=enriched_dto.status,
                start_date=enriched_dto.start_date,
                end_date=enriched_dto.end_date,
                country_code=enriched_dto.country_code,
                secondary_country_code=enriched_dto.secondary_country_code,
                tertiary_country_code=enriched_dto.tertiary_country_code,
                location=enriched_dto.location,
                handicap_type=enriched_dto.handicap_type,
                handicap_percentage=enriched_dto.handicap_percentage,
                max_players=enriched_dto.max_players,
                team_assignment=enriched_dto.team_assignment,
                is_creator=True,  # Siempre True para el creador
                enrolled_count=0,  # Siempre 0 al crear
                created_at=enriched_dto.created_at,
                updated_at=enriched_dto.updated_at,
            )

    except CompetitionAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=List[CompetitionResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar competiciones con filtros",
    description="Obtiene lista de competiciones con filtros opcionales.",
    tags=["Competitions"],
)
async def list_competitions(
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ListCompetitionsUseCase = Depends(get_list_competitions_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por estado (DRAFT, ACTIVE, etc.)"),
    creator_id: Optional[str] = Query(None, description="Filtrar por creador (UUID)"),
):
    """
    Endpoint para listar competiciones con filtros opcionales.

    **Query Parameters:**
    - status: Filtrar por estado (ej: ACTIVE, DRAFT, CLOSED)
    - creator_id: Filtrar por creador (UUID del usuario)

    **Returns:**
    - Lista de competiciones con campos calculados:
      - is_creator: True si el usuario autenticado es el creador
      - enrolled_count: Número de jugadores aprobados
      - location: String formateado (ej: "Spain, France")
    """
    try:
        current_user_id = UserId(str(current_user.id))

        # Ejecutar use case (retorna entidades)
        competitions = await use_case.execute(
            status=status_filter,
            creator_id=creator_id,
        )

        # Convertir entidades a DTOs enriquecidos
        result = []
        async with uow:
            for competition in competitions:
                dto = await CompetitionDTOMapper.to_response_dto(
                    competition, current_user_id, uow
                )
                result.append(dto)

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{competition_id}",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Obtener competición por ID",
    description="Obtiene el detalle completo de una competición.",
    tags=["Competitions"],
)
async def get_competition(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetCompetitionUseCase = Depends(get_get_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
):
    """
    Endpoint para obtener el detalle de una competición.

    **Path Parameters:**
    - competition_id: UUID de la competición

    **Returns:**
    - Competición completa con campos calculados
    """
    try:
        current_user_id = UserId(str(current_user.id))
        competition_vo_id = CompetitionId(competition_id)

        # Ejecutar use case (retorna entidad)
        competition = await use_case.execute(competition_vo_id)

        if not competition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Competition with ID {competition_id} not found",
            )

        # Convertir a DTO enriquecido
        async with uow:
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow
            )

        return dto

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/{competition_id}",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar competición",
    description="Actualiza una competición (SOLO en estado DRAFT y SOLO el creador).",
    tags=["Competitions"],
)
async def update_competition(
    competition_id: UUID,
    request: UpdateCompetitionRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: UpdateCompetitionUseCase = Depends(get_update_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
):
    """
    Endpoint para actualizar una competición.

    **Restricciones:**
    - Solo el creador puede actualizar
    - Solo en estado DRAFT
    - Actualización parcial (solo campos enviados)

    **Request Body:** Todos los campos opcionales
    - name, start_date, end_date
    - main_country, adjacent_country_1, adjacent_country_2
    - handicap_type, handicap_percentage
    - max_players, team_assignment

    **Returns:**
    - Competición actualizada
    """
    try:
        current_user_id = UserId(str(current_user.id))
        competition_vo_id = CompetitionId(competition_id)

        # Verificar autorización
        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            if not competition:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Competition with ID {competition_id} not found",
                )

            if competition.creator_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the creator can update this competition",
                )

        # Ejecutar use case
        updated_competition = await use_case.execute(competition_vo_id, request)

        # Convertir a DTO enriquecido
        async with uow:
            dto = await CompetitionDTOMapper.to_response_dto(
                updated_competition, current_user_id, uow
            )

        return dto

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{competition_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar competición",
    description="Elimina físicamente una competición (SOLO en estado DRAFT y SOLO el creador).",
    tags=["Competitions"],
)
async def delete_competition(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: DeleteCompetitionUseCase = Depends(get_delete_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
):
    """
    Endpoint para eliminar físicamente una competición.

    **Restricciones:**
    - Solo el creador puede eliminar
    - Solo en estado DRAFT
    - Eliminación permanente (no se puede deshacer)

    **Returns:**
    - 204 No Content si es exitoso
    """
    try:
        current_user_id = UserId(str(current_user.id))
        competition_vo_id = CompetitionId(competition_id)

        # Verificar autorización
        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            if not competition:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Competition with ID {competition_id} not found",
                )

            if competition.creator_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the creator can delete this competition",
                )

        # Ejecutar use case
        await use_case.execute(competition_vo_id)

        return None

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ======================================================================================
# STATE TRANSITION ENDPOINTS
# ======================================================================================

@router.post(
    "/{competition_id}/activate",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Activar competición (DRAFT → ACTIVE)",
    description="Activa una competición para abrir inscripciones. Solo el creador.",
    tags=["Competitions - State Transitions"],
)
async def activate_competition(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ActivateCompetitionUseCase = Depends(get_activate_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
):
    """
    Transición de estado: DRAFT → ACTIVE

    **Restricciones:**
    - Solo el creador
    - Solo desde DRAFT

    **Returns:**
    - Competición con status=ACTIVE
    """
    try:
        current_user_id = UserId(str(current_user.id))
        competition_vo_id = CompetitionId(competition_id)

        # Verificar autorización
        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            if not competition:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Competition with ID {competition_id} not found",
                )

            if competition.creator_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the creator can activate this competition",
                )

        # Ejecutar use case
        updated_competition = await use_case.execute(competition_vo_id)

        # Convertir a DTO
        async with uow:
            dto = await CompetitionDTOMapper.to_response_dto(
                updated_competition, current_user_id, uow
            )

        return dto

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{competition_id}/close-enrollments",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Cerrar inscripciones (ACTIVE → CLOSED)",
    description="Cierra las inscripciones de una competición. Solo el creador.",
    tags=["Competitions - State Transitions"],
)
async def close_enrollments(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CloseEnrollmentsUseCase = Depends(get_close_enrollments_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
):
    """
    Transición de estado: ACTIVE → CLOSED

    **Restricciones:**
    - Solo el creador
    - Solo desde ACTIVE

    **Returns:**
    - Competición con status=CLOSED
    """
    try:
        current_user_id = UserId(str(current_user.id))
        competition_vo_id = CompetitionId(competition_id)

        # Verificar autorización
        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            if not competition:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Competition with ID {competition_id} not found",
                )

            if competition.creator_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the creator can close enrollments",
                )

        # Ejecutar use case
        updated_competition = await use_case.execute(competition_vo_id)

        # Convertir a DTO
        async with uow:
            dto = await CompetitionDTOMapper.to_response_dto(
                updated_competition, current_user_id, uow
            )

        return dto

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{competition_id}/start",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Iniciar competición (CLOSED → IN_PROGRESS)",
    description="Inicia el torneo. Solo el creador.",
    tags=["Competitions - State Transitions"],
)
async def start_competition(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: StartCompetitionUseCase = Depends(get_start_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
):
    """
    Transición de estado: CLOSED → IN_PROGRESS

    **Restricciones:**
    - Solo el creador
    - Solo desde CLOSED

    **Returns:**
    - Competición con status=IN_PROGRESS
    """
    try:
        current_user_id = UserId(str(current_user.id))
        competition_vo_id = CompetitionId(competition_id)

        # Verificar autorización
        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            if not competition:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Competition with ID {competition_id} not found",
                )

            if competition.creator_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the creator can start this competition",
                )

        # Ejecutar use case
        updated_competition = await use_case.execute(competition_vo_id)

        # Convertir a DTO
        async with uow:
            dto = await CompetitionDTOMapper.to_response_dto(
                updated_competition, current_user_id, uow
            )

        return dto

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{competition_id}/complete",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Completar competición (IN_PROGRESS → COMPLETED)",
    description="Finaliza el torneo. Solo el creador.",
    tags=["Competitions - State Transitions"],
)
async def complete_competition(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CompleteCompetitionUseCase = Depends(get_complete_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
):
    """
    Transición de estado: IN_PROGRESS → COMPLETED

    **Restricciones:**
    - Solo el creador
    - Solo desde IN_PROGRESS

    **Returns:**
    - Competición con status=COMPLETED
    """
    try:
        current_user_id = UserId(str(current_user.id))
        competition_vo_id = CompetitionId(competition_id)

        # Verificar autorización
        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            if not competition:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Competition with ID {competition_id} not found",
                )

            if competition.creator_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the creator can complete this competition",
                )

        # Ejecutar use case
        updated_competition = await use_case.execute(competition_vo_id)

        # Convertir a DTO
        async with uow:
            dto = await CompetitionDTOMapper.to_response_dto(
                updated_competition, current_user_id, uow
            )

        return dto

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{competition_id}/cancel",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Cancelar competición (cualquier estado → CANCELLED)",
    description="Cancela una competición. Solo el creador.",
    tags=["Competitions - State Transitions"],
)
async def cancel_competition(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CancelCompetitionUseCase = Depends(get_cancel_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
):
    """
    Transición de estado: cualquier estado → CANCELLED

    **Restricciones:**
    - Solo el creador
    - No se puede cancelar si ya está COMPLETED o CANCELLED

    **Returns:**
    - Competición con status=CANCELLED
    """
    try:
        current_user_id = UserId(str(current_user.id))
        competition_vo_id = CompetitionId(competition_id)

        # Verificar autorización
        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            if not competition:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Competition with ID {competition_id} not found",
                )

            if competition.creator_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the creator can cancel this competition",
                )

        # Ejecutar use case (puede recibir reason opcional)
        updated_competition = await use_case.execute(competition_vo_id, reason=None)

        # Convertir a DTO
        async with uow:
            dto = await CompetitionDTOMapper.to_response_dto(
                updated_competition, current_user_id, uow
            )

        return dto

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
