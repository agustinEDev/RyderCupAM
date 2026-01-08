"""
Competition Routes - API REST Layer (Infrastructure).

Endpoints FastAPI para el módulo Competition siguiendo Clean Architecture.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from src.config.dependencies import (
    get_activate_competition_use_case,
    get_cancel_competition_use_case,
    get_close_enrollments_use_case,
    get_competition_uow,
    get_complete_competition_use_case,
    get_create_competition_use_case,
    get_current_user,
    get_delete_competition_use_case,
    get_get_competition_use_case,
    get_list_competitions_use_case,
    get_start_competition_use_case,
    get_uow,  # User Unit of Work para obtener datos del creador
    get_update_competition_use_case,
)
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.competition_dto import (
    ActivateCompetitionRequestDTO,
    CancelCompetitionRequestDTO,
    CloseEnrollmentsRequestDTO,
    CompetitionResponseDTO,
    CompleteCompetitionRequestDTO,
    CountryResponseDTO,
    CreateCompetitionRequestDTO,
    CreateCompetitionResponseDTO,
    CreatorDTO,
    DeleteCompetitionRequestDTO,
    StartCompetitionRequestDTO,
    UpdateCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.activate_competition_use_case import (
    ActivateCompetitionUseCase,
    CompetitionNotFoundError as ActivateNotFoundError,
    NotCompetitionCreatorError as ActivateNotCreatorError,
)
from src.modules.competition.application.use_cases.cancel_competition_use_case import (
    CancelCompetitionUseCase,
    CompetitionNotFoundError as CancelNotFoundError,
    NotCompetitionCreatorError as CancelNotCreatorError,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
    CompetitionNotFoundError as CloseNotFoundError,
    NotCompetitionCreatorError as CloseNotCreatorError,
)
from src.modules.competition.application.use_cases.complete_competition_use_case import (
    CompetitionNotFoundError as CompleteNotFoundError,
    CompleteCompetitionUseCase,
    NotCompetitionCreatorError as CompleteNotCreatorError,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CompetitionAlreadyExistsError,
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.delete_competition_use_case import (
    CompetitionNotDeletableError,
    CompetitionNotFoundError as DeleteNotFoundError,
    DeleteCompetitionUseCase,
    NotCompetitionCreatorError as DeleteNotCreatorError,
)
from src.modules.competition.application.use_cases.get_competition_use_case import (
    CompetitionNotFoundError as GetNotFoundError,
    GetCompetitionUseCase,
)
from src.modules.competition.application.use_cases.list_competitions_use_case import (
    ListCompetitionsUseCase,
)
from src.modules.competition.application.use_cases.start_competition_use_case import (
    CompetitionNotFoundError as StartNotFoundError,
    NotCompetitionCreatorError as StartNotCreatorError,
    StartCompetitionUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    CompetitionNotEditableError,
    CompetitionNotFoundError as UpdateNotFoundError,
    NotCompetitionCreatorError as UpdateNotCreatorError,
    UpdateCompetitionUseCase,
)
from src.modules.competition.domain.entities.competition import Competition, CompetitionStateError
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.location_builder import InvalidCountryError
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.repositories.user_unit_of_work_interface import UserUnitOfWorkInterface
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)

# ======================================================================================
# HELPER FUNCTIONS
# ======================================================================================


# Helpers privados para modularidad y menor complejidad


def _sanitize_creator_id(creator_id: str | None) -> str | None:
    if creator_id and creator_id not in ("undefined", "null", ""):
        return creator_id
    return None

async def _fetch_competitions_by_status(use_case, status_filter, creator_id, search_name, search_creator):
    """
    Obtiene competiciones aplicando filtros de status (soporte para lista o string único).

    Args:
        status_filter: None, string único, o lista de strings

    Returns:
        Lista de competiciones sin duplicados
    """
    if isinstance(status_filter, list) and len(status_filter) > 0:
        all_competitions = []
        for status in status_filter:
            comps = await use_case.execute(
                status=status,
                creator_id=creator_id,
                search_name=search_name,
                search_creator=search_creator,
            )
            all_competitions.extend(comps)
        # Eliminar duplicados basados en ID
        return list({c.id: c for c in all_competitions}.values())

    # status_filter es None o un solo string
    return await use_case.execute(
        status=status_filter if not isinstance(status_filter, list) else None,
        creator_id=creator_id,
        search_name=search_name,
        search_creator=search_creator,
    )

def _should_exclude_enrollment(enrollment_status, competition_status):
    """
    Determina si una competición inscrita debe excluirse de los resultados.

    LÓGICA DE EXCLUSIÓN: No mostrar competiciones rechazadas si no están ACTIVE.
    """
    return enrollment_status == EnrollmentStatus.REJECTED and competition_status != 'ACTIVE'

def _matches_status_filter(competition_status, status_filter):
    """
    Verifica si una competición cumple con el filtro de status.

    Args:
        competition_status: Status actual de la competición (string)
        status_filter: None, string único, o lista de strings

    Returns:
        True si la competición debe incluirse, False en caso contrario
    """
    if not status_filter:
        return True

    if isinstance(status_filter, list):
        return competition_status in [s.upper() for s in status_filter]

    return competition_status == status_filter.upper()

async def _fetch_enrolled_competitions(uow, enrollments, created_competition_ids, status_filter, enrollment_status_map):
    """
    Obtiene las competiciones donde el usuario está inscrito (excluyendo las que ya creó).

    Args:
        uow: Unit of Work
        enrollments: Lista de enrollments del usuario
        created_competition_ids: IDs de competiciones ya creadas por el usuario
        status_filter: Filtro de status
        enrollment_status_map: Mapa de enrollment_status por competition_id

    Returns:
        Lista de competiciones inscritas que cumplen los criterios
    """
    enrolled_competition_ids = {enrollment.competition_id for enrollment in enrollments}
    enrolled_competitions = []

    for comp_id in enrolled_competition_ids:
        competition = await uow.competitions.find_by_id(comp_id)

        if not competition or competition.id in created_competition_ids:
            continue

        enrollment_status = enrollment_status_map.get(competition.id)

        # Aplicar lógica de exclusión
        if _should_exclude_enrollment(enrollment_status, competition.status.value):
            continue

        # Aplicar filtro de status
        if _matches_status_filter(competition.status.value, status_filter):
            enrolled_competitions.append(competition)

    return enrolled_competitions

async def _get_user_competitions(uow, use_case, current_user_id, status_filter, search_name, search_creator):
    """
    Obtiene competiciones donde el usuario es creador O está inscrito.

    Args:
        status_filter: Puede ser None, un string, o una lista de strings

    Returns:
        Lista combinada de competiciones creadas e inscritas
    """
    async with uow:
        # Obtener competiciones creadas por el usuario
        created_competitions = await _fetch_competitions_by_status(
            use_case,
            status_filter,
            str(current_user_id.value),
            search_name,
            search_creator
        )

        # Obtener enrollments del usuario
        enrollments = await uow.enrollments.find_by_user(current_user_id)

        # Crear mapa de enrollment_status por competition_id
        enrollment_status_map = {enrollment.competition_id: enrollment.status for enrollment in enrollments}

        # Obtener IDs de competiciones creadas para evitar duplicados
        created_competition_ids = [c.id for c in created_competitions]

        # Obtener competiciones donde el usuario está inscrito
        enrolled_competitions = await _fetch_enrolled_competitions(
            uow,
            enrollments,
            created_competition_ids,
            status_filter,
            enrollment_status_map
        )

        return created_competitions + enrolled_competitions

async def _map_competitions_to_dtos(competitions, current_user_id, uow, user_uow):
    result = []
    async with uow:
        for competition in competitions:
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )
            result.append(dto)
    return result

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
        user_uow: UserUnitOfWorkInterface | None = None,
    ) -> CompetitionResponseDTO:
        """
        Convierte una entidad Competition a CompetitionResponseDTO.

        Calcula campos dinámicos:
        - is_creator: si el usuario actual es el creador
        - enrolled_count: número de enrollments APPROVED
        - location: string formateado con nombres de países
        - creator: información completa del creador (si user_uow es provisto)

        Args:
            competition: Entidad de dominio
            current_user_id: ID del usuario autenticado
            uow: Unit of Work para consultas adicionales (enrollments, countries)
            user_uow: Unit of Work de usuarios para obtener datos del creador (opcional)

        Returns:
            CompetitionResponseDTO enriquecido
        """
        # Calcular enrolled_count
        enrolled_count = await uow.enrollments.count_approved(competition.id)

        # Calcular pending_enrollments_count (solicitudes pendientes)
        pending_enrollments_count = await uow.enrollments.count_pending(competition.id)

        # Obtener enrollment status del usuario actual (si existe)
        user_enrollment_status = None
        try:
            user_enrollments = await uow.enrollments.find_by_user(current_user_id)
            # Filtrar por esta competición específica
            user_enrollment = next(
                (e for e in user_enrollments if e.competition_id == competition.id),
                None
            )
            if user_enrollment:
                user_enrollment_status = user_enrollment.status.value if hasattr(user_enrollment.status, 'value') else user_enrollment.status
                logger.info(f"✅ Found enrollment for user {current_user_id.value} in competition {competition.id.value}: {user_enrollment_status}")
            else:
                logger.info(f"[INFO] No enrollment found for user {current_user_id.value} in competition {competition.id.value}")
        except Exception as e:
            logger.error(f"❌ Error fetching user enrollment: {e}")
            user_enrollment_status = None

        # Formatear location
        location_str = await CompetitionDTOMapper._format_location(competition, uow)

        # Obtener lista de países con detalles
        countries_list = await CompetitionDTOMapper._get_countries_list(competition, uow)

        # Obtener información del creador (si user_uow es provisto)
        creator_dto = None
        if user_uow:
            creator_dto = await CompetitionDTOMapper._get_creator_dto(competition.creator_id, user_uow)

        # Construir DTO
        return CompetitionResponseDTO(
            id=competition.id.value,
            creator_id=competition.creator_id.value,
            creator=creator_dto,
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
            # Location - countries array
            countries=countries_list,
            # Handicap
            handicap_type=competition.handicap_settings.type.value,
            handicap_percentage=competition.handicap_settings.percentage,
            # Config
            max_players=competition.max_players,
            team_assignment=competition.team_assignment.value if hasattr(competition.team_assignment, 'value') else competition.team_assignment,
            # Teams
            team_1_name=competition.team_1_name,
            team_2_name=competition.team_2_name,
            # Campos calculados
            is_creator=(competition.creator_id == current_user_id),
            enrolled_count=enrolled_count,
            pending_enrollments_count=pending_enrollments_count,
            user_enrollment_status=user_enrollment_status,
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

    @staticmethod
    async def _get_countries_list(
        competition: Competition,
        uow: CompetitionUnitOfWorkInterface,
    ) -> list[CountryResponseDTO]:
        """
        Obtiene la lista completa de países participantes con códigos y nombres.

        Args:
            competition: Entidad Competition
            uow: Unit of Work para consultar países

        Returns:
            Lista de CountryResponseDTO
        """
        location = competition.location
        countries = []

        # País principal
        main_country = await uow.countries.find_by_code(location.main_country)
        if main_country:
            countries.append(CountryResponseDTO(
                code=main_country.code.value,  # Extraer valor primitivo del value object
                name_en=main_country.name_en,
                name_es=main_country.name_es
            ))

        # País adyacente 1
        if location.adjacent_country_1:
            country = await uow.countries.find_by_code(location.adjacent_country_1)
            if country:
                countries.append(CountryResponseDTO(
                    code=country.code.value,  # Extraer valor primitivo del value object
                    name_en=country.name_en,
                    name_es=country.name_es
                ))

        # País adyacente 2
        if location.adjacent_country_2:
            country = await uow.countries.find_by_code(location.adjacent_country_2)
            if country:
                countries.append(CountryResponseDTO(
                    code=country.code.value,  # Extraer valor primitivo del value object
                    name_en=country.name_en,
                    name_es=country.name_es
                ))

        return countries

    @staticmethod
    async def _get_creator_dto(
        creator_id: UserId,
        user_uow: UserUnitOfWorkInterface,
    ) -> CreatorDTO | None:
        """
        Obtiene la información del creador de una competición.

        Args:
            creator_id: ID del usuario creador
            user_uow: Unit of Work de usuarios

        Returns:
            CreatorDTO con los datos del creador, o None si no se encuentra
        """
        async with user_uow:
            creator = await user_uow.users.find_by_id(creator_id)

            if not creator:
                logger.warning(f"Creator with id {creator_id.value} not found")
                return None

            return CreatorDTO(
                id=creator.id.value,
                first_name=creator.first_name,
                last_name=creator.last_name,
                email=str(creator.email),
                handicap=creator.handicap.value if creator.handicap else None,
                country_code=creator.country_code.value if creator.country_code else None,
            )


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
@limiter.limit("10/hour")  # Anti-spam: máximo 10 competiciones nuevas por hora
async def create_competition(
    request: Request,  # noqa: ARG001 - Requerido por SlowAPI limiter
    competition_data: CreateCompetitionRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CreateCompetitionUseCase = Depends(get_create_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
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
        response = await use_case.execute(competition_data, creator_id)

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
                competition, creator_id, uow, user_uow
            )

            # Construir CreateCompetitionResponseDTO con todos los campos
            return CreateCompetitionResponseDTO(
                id=enriched_dto.id,
                creator_id=enriched_dto.creator_id,
                creator=enriched_dto.creator,
                name=enriched_dto.name,
                status=enriched_dto.status,
                start_date=enriched_dto.start_date,
                end_date=enriched_dto.end_date,
                country_code=enriched_dto.country_code,
                secondary_country_code=enriched_dto.secondary_country_code,
                tertiary_country_code=enriched_dto.tertiary_country_code,
                location=enriched_dto.location,
                countries=enriched_dto.countries,
                handicap_type=enriched_dto.handicap_type,
                handicap_percentage=enriched_dto.handicap_percentage,
                max_players=enriched_dto.max_players,
                team_assignment=enriched_dto.team_assignment,
                team_1_name=competition.team_1_name,
                team_2_name=competition.team_2_name,
                is_creator=True,  # Siempre True para el creador
                enrolled_count=0,  # Siempre 0 al crear
                created_at=enriched_dto.created_at,
                updated_at=enriched_dto.updated_at,
            )

    except CompetitionAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except InvalidCountryError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


async def _get_all_competitions(use_case, status_filter, creator_id, search_name, search_creator):
    """
    Obtiene todas las competiciones aplicando filtros (sin filtrar por usuario).

    Returns:
        Lista de competiciones sin duplicados
    """
    return await _fetch_competitions_by_status(
        use_case,
        status_filter,
        creator_id,
        search_name,
        search_creator
    )

async def _exclude_user_competitions(competitions, current_user_id, uow):
    """
    Excluye competiciones donde el usuario es creador o está inscrito.

    Args:
        competitions: Lista de competiciones a filtrar
        current_user_id: ID del usuario actual
        uow: Unit of Work

    Returns:
        Lista de competiciones filtrada
    """
    # Get user's enrollments to exclude competitions where user is enrolled
    enrollments = await uow.enrollments.find_by_user(current_user_id)
    enrolled_competition_ids = {enrollment.competition_id for enrollment in enrollments}

    # Filter out: competitions created by user OR competitions where user has enrollment
    return [
        comp for comp in competitions
        if comp.creator_id != current_user_id and comp.id not in enrolled_competition_ids
    ]

@router.get(
    "",
    response_model=list[CompetitionResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar competiciones con filtros",
    description="Obtiene lista de competiciones con filtros opcionales.",
    tags=["Competitions"],
)
async def list_competitions(
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ListCompetitionsUseCase = Depends(get_list_competitions_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    status_filter: list[str] | None = Query(None, alias="status", description="Filtrar por estado (puede recibir múltiples valores: DRAFT, ACTIVE, CLOSED, IN_PROGRESS, COMPLETED)"),
    creator_id: str | None = Query(None, description="Filtrar por creador (UUID)"),
    my_competitions: bool | None = Query(None, description="Si es True, devuelve competiciones donde el usuario es creador o está inscrito. Si es False, excluye esas competiciones. Si es None (por defecto), devuelve todas."),
    search_name: str | None = Query(None, description="Buscar por nombre de competición (parcial, case-insensitive)"),
    search_creator: str | None = Query(None, description="Buscar por nombre del creador (parcial, case-insensitive)"),
):
    """
    Endpoint para listar competiciones con filtros opcionales.

    **Query Parameters:**
    - status: Filtrar por estado (ej: ACTIVE, DRAFT, CLOSED)
    - creator_id: Filtrar por creador (UUID del usuario)
    - my_competitions: Si es True, solo muestra competiciones del usuario (creadas o inscritas)
    - search_name: Búsqueda parcial en el nombre de la competición
    - search_creator: Búsqueda parcial en el nombre del creador

    **Returns:**
    - Lista de competiciones con campos calculados:
      - is_creator: True si el usuario autenticado es el creador
      - enrolled_count: Número de jugadores aprobados
      - location: String formateado (ej: "Spain, France")
    """
    try:
        current_user_id = UserId(str(current_user.id))
        sanitized_creator_id = _sanitize_creator_id(creator_id)

        if my_competitions is True:
            # Return only competitions where user is creator OR enrolled
            competitions = await _get_user_competitions(
                uow, use_case, current_user_id, status_filter, search_name, search_creator
            )
        elif my_competitions is False:
            # Explicitly exclude competitions where user is creator OR enrolled
            competitions = await _get_all_competitions(
                use_case, status_filter, sanitized_creator_id, search_name, search_creator
            )

            # Filter out competitions where user is creator or has enrollment
            async with uow:
                competitions = await _exclude_user_competitions(competitions, current_user_id, uow)
        else:
            # my_competitions is None: return all competitions (no filtering by user relationship)
            competitions = await _get_all_competitions(
                use_case, status_filter, sanitized_creator_id, search_name, search_creator
            )

        result = await _map_competitions_to_dtos(competitions, current_user_id, uow, user_uow)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


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
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
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

        # Ejecutar use case (retorna entidad o lanza excepción)
        competition = await use_case.execute(competition_vo_id)

        # Convertir a DTO enriquecido
        async with uow:
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except GetNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


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
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
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

        # Ejecutar use case
        await use_case.execute(competition_vo_id, request, current_user_id)

        # Obtener la competición actualizada para el DTO de respuesta
        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except UpdateNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except UpdateNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (CompetitionNotEditableError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


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
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),  # noqa: ARG001
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),  # noqa: ARG001
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

        # Crear DTO de request
        request_dto = DeleteCompetitionRequestDTO(competition_id=competition_id)

        # Ejecutar use case
        await use_case.execute(request_dto, current_user_id)

        return

    except DeleteNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except DeleteNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (CompetitionNotDeletableError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


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
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
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

        # Crear DTO de request
        request_dto = ActivateCompetitionRequestDTO(competition_id=competition_id)

        # Ejecutar use case (valida existencia, autorización y estado)
        await use_case.execute(request_dto, current_user_id)

        # Obtener la competición actualizada para el DTO de respuesta
        competition_vo_id = CompetitionId(competition_id)
        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except ActivateNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ActivateNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (CompetitionStateError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


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
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
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

        # Crear DTO de request
        request_dto = CloseEnrollmentsRequestDTO(competition_id=competition_id)

        # Ejecutar use case
        await use_case.execute(request_dto, current_user_id)

        # Obtener la competición actualizada para el DTO de respuesta
        competition_vo_id = CompetitionId(competition_id)
        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except CloseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except CloseNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (CompetitionStateError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


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
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
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

        # Crear DTO de request
        request_dto = StartCompetitionRequestDTO(competition_id=competition_id)

        # Ejecutar use case
        await use_case.execute(request_dto, current_user_id)

        # Obtener la competición actualizada para el DTO de respuesta
        competition_vo_id = CompetitionId(competition_id)
        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except StartNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except StartNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (CompetitionStateError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


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
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
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

        # Crear DTO de request
        request_dto = CompleteCompetitionRequestDTO(competition_id=competition_id)

        # Ejecutar use case
        await use_case.execute(request_dto, current_user_id)

        # Obtener la competición actualizada para el DTO de respuesta
        competition_vo_id = CompetitionId(competition_id)
        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except CompleteNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except CompleteNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (CompetitionStateError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


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
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
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

        # Crear DTO de request (reason es opcional)
        request_dto = CancelCompetitionRequestDTO(competition_id=competition_id)

        # Ejecutar use case
        await use_case.execute(request_dto, current_user_id)

        # Obtener la competición actualizada para el DTO de respuesta
        competition_vo_id = CompetitionId(competition_id)
        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except CancelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except CancelNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (CompetitionStateError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
