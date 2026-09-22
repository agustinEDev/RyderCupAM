"""Competition CRUD Routes - Create, Read, Update, Delete endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from src.config.dependencies import (
    get_competition_uow,
    get_create_competition_use_case,
    get_current_user,
    get_delete_competition_use_case,
    get_get_competition_use_case,
    get_list_competitions_use_case,
    get_uow,
    get_update_competition_use_case,
)
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.competition_dto import (
    CompetitionResponseDTO,
    CreateCompetitionRequestDTO,
    CreateCompetitionResponseDTO,
    DeleteCompetitionRequestDTO,
    UpdateCompetitionRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.mappers.competition_mapper import (
    CompetitionDTOMapper,
)
from src.modules.competition.application.services.enrollment_opener import (
    EnrollmentOpener,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CompetitionAlreadyExistsError,
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.delete_competition_use_case import (
    CompetitionNotDeletableError,
    DeleteCompetitionUseCase,
)
from src.modules.competition.application.use_cases.get_competition_use_case import (
    GetCompetitionUseCase,
)
from src.modules.competition.application.use_cases.list_competitions_use_case import (
    ListCompetitionsUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    CompetitionNotEditableError,
    UpdateCompetitionUseCase,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.location_builder import InvalidCountryError
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import (
    EnrollmentStatus,
)
from src.modules.competition.domain.value_objects.location import InvalidLocationError
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import InvalidCountryCodeError

logger = logging.getLogger(__name__)

router = APIRouter()


# ======================================================================================
# HELPER FUNCTIONS (for list endpoint)
# ======================================================================================


def _sanitize_creator_id(creator_id: str | None) -> str | None:
    if creator_id and creator_id not in ("undefined", "null", ""):
        return creator_id
    return None


async def _fetch_competitions_by_status(
    use_case, status_filter, creator_id, search_name, search_creator, viewer_id=None, is_admin=False
):
    """Obtiene competiciones aplicando filtros de status (soporte para lista o string único)."""
    if isinstance(status_filter, list) and len(status_filter) > 0:
        all_competitions = []
        for comp_status in status_filter:
            comps = await use_case.execute(
                status=comp_status,
                creator_id=creator_id,
                search_name=search_name,
                search_creator=search_creator,
                viewer_id=viewer_id,
                is_admin=is_admin,
            )
            all_competitions.extend(comps)
        return list({c.id: c for c in all_competitions}.values())

    return await use_case.execute(
        status=status_filter if not isinstance(status_filter, list) else None,
        creator_id=creator_id,
        search_name=search_name,
        search_creator=search_creator,
        viewer_id=viewer_id,
        is_admin=is_admin,
    )


def _should_exclude_enrollment(enrollment_status, competition_status):
    """Determina si una competición inscrita debe excluirse de los resultados."""
    return enrollment_status == EnrollmentStatus.REJECTED and competition_status != "ACTIVE"


def _matches_status_filter(competition_status, status_filter):
    """Verifica si una competición cumple con el filtro de status."""
    if not status_filter:
        return True
    if isinstance(status_filter, list):
        return competition_status in [s.upper() for s in status_filter]
    return competition_status == status_filter.upper()


async def _fetch_enrolled_competitions(uow, enrollments, created_competition_ids):
    """Las competiciones donde el usuario está inscrito, sin filtrar por estado.

    Solo las trae. Los filtros que dependen del estado van en
    `_filtrar_inscritas`, y se aplican después de abrir las que toquen: este
    camino no pasa por `ListCompetitionsUseCase`, así que la apertura programada
    hay que aplicarla aquí también o «Mis competiciones» seguiría enseñando en
    borrador la competición a la que a uno le invitaron, pasado su día (BE #331).
    """
    enrolled_competition_ids = {enrollment.competition_id for enrollment in enrollments}
    candidatas = []

    for comp_id in enrolled_competition_ids:
        competition = await uow.competitions.find_by_id(comp_id)

        if not competition or competition.id in created_competition_ids:
            continue

        candidatas.append(competition)

    return candidatas


def _filtrar_inscritas(competitions, status_filter, enrollment_status_map):
    """Aplica los filtros que dependen del ESTADO, ya con el estado definitivo.

    Va después de abrir las que tocan: hacerlo antes filtraría por el estado
    viejo, y una competición que acaba de abrirse se descartaría o se enseñaría
    cerrada (BE #331).
    """
    resultado = []
    for competition in competitions:
        enrollment_status = enrollment_status_map.get(competition.id)

        if _should_exclude_enrollment(enrollment_status, competition.status.value):
            continue

        if _matches_status_filter(competition.status.value, status_filter):
            resultado.append(competition)

    return resultado


async def _get_user_competitions(
    uow, use_case, current_user_id, status_filter, search_name, search_creator
):
    """Obtiene competiciones donde el usuario es creador O está inscrito.

    Assumes caller manages the uow transaction context.
    """
    created_competitions = await _fetch_competitions_by_status(
        use_case,
        status_filter,
        str(current_user_id.value),
        search_name,
        search_creator,
        viewer_id=str(current_user_id.value),
    )

    enrollments = await uow.enrollments.find_by_user(current_user_id)

    enrollment_status_map = {
        enrollment.competition_id: enrollment.status for enrollment in enrollments
    }

    created_competition_ids = [c.id for c in created_competitions]

    candidatas = await _fetch_enrolled_competitions(uow, enrollments, created_competition_ids)

    # Las que salen de tus inscripciones tambien pasan por el filtro: una fila
    # rechazada o retirada no se borra, y sin esto el expulsado recuperaba la
    # privada por aqui (BE #318, punto gemelo del listado)
    visibles = await use_case.visibles_para(candidatas, str(current_user_id.value))

    # Abrir DESPUES de la visibilidad y ANTES del filtro por estado, igual que
    # hace el caso de uso: a quien no se le ensena una privada tampoco se le
    # abre de paso, y filtrar por el estado viejo tiraria la recien abierta
    await EnrollmentOpener.abrir_las_que_toquen(visibles, uow, use_case.zona_del_campo)

    return created_competitions + _filtrar_inscritas(
        visibles, status_filter, enrollment_status_map
    )


async def _map_competitions_to_dtos(competitions, current_user_id, uow, user_uow, is_admin=False):
    """Convierte entidades Competition a DTOs.

    Assumes caller manages the uow/user_uow transaction context.
    """
    result = []
    for competition in competitions:
        dto = await CompetitionDTOMapper.to_response_dto(
            competition, current_user_id, uow, user_uow, is_admin=is_admin
        )
        result.append(dto)
    return result


async def _get_all_competitions(
    use_case, status_filter, creator_id, search_name, search_creator, viewer_id=None, is_admin=False
):
    """Obtiene todas las competiciones aplicando filtros (sin filtrar por usuario).

    `viewer_id` no es opcional de verdad: sin el, las privadas de otros saldrian
    en la pantalla de explorar, que es lo que BE #318 vino a arreglar.
    """
    return await _fetch_competitions_by_status(
        use_case, status_filter, creator_id, search_name, search_creator, viewer_id, is_admin
    )


async def _exclude_user_competitions(competitions, current_user_id, uow):
    """Excluye competiciones donde el usuario es creador o está inscrito."""
    enrollments = await uow.enrollments.find_by_user(current_user_id)
    enrolled_competition_ids = {enrollment.competition_id for enrollment in enrollments}

    return [
        comp
        for comp in competitions
        if comp.creator_id != current_user_id and comp.id not in enrolled_competition_ids
    ]


# ======================================================================================
# CRUD ENDPOINTS
# ======================================================================================


@router.post(
    "",
    response_model=CreateCompetitionResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva competición",
    description="Crea una nueva competición. Nace con las inscripciones ABIERTAS salvo que se indique `enrollment_opens_days_before`, en cuyo caso espera en DRAFT hasta su apertura. Requiere autenticación.",
    tags=["Competitions"],
)
@limiter.limit("10/hour")
async def create_competition(
    request: Request,  # noqa: ARG001 - Requerido por SlowAPI limiter
    competition_data: CreateCompetitionRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CreateCompetitionUseCase = Depends(get_create_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
):
    """Endpoint para crear una nueva competición."""
    try:
        creator_id = UserId(str(current_user.id))

        response = await use_case.execute(competition_data, creator_id)

        async with uow, user_uow:
            competition = await uow.competitions.find_by_id(CompetitionId(response.id))

            if not competition:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Competition created but not found",
                )

            enriched_dto = await CompetitionDTOMapper.to_response_dto(
                competition, creator_id, uow, user_uow
            )

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
                play_mode=enriched_dto.play_mode,
                max_players=enriched_dto.max_players,
                team_assignment=enriched_dto.team_assignment,
                enrollment_opens_days_before=competition.enrollment_opens_days_before,
                visibility=str(competition.visibility),
                setup_mode=str(competition.setup_mode),
                team_1_name=competition.team_1_name,
                team_2_name=competition.team_2_name,
                is_creator=True,
                enrolled_count=0,
                created_at=enriched_dto.created_at,
                updated_at=enriched_dto.updated_at,
            )

    except CompetitionAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except (InvalidCountryError, InvalidCountryCodeError, InvalidLocationError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "",
    response_model=list[CompetitionResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar competiciones con filtros",
    description="Obtiene lista de competiciones con filtros opcionales.",
    tags=["Competitions"],
)
@limiter.limit("30/minute")
async def list_competitions(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ListCompetitionsUseCase = Depends(get_list_competitions_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    status_filter: list[str] | None = Query(
        None,
        alias="status",
        description="Filtrar por estado (puede recibir múltiples valores)",
    ),
    creator_id: str | None = Query(None, description="Filtrar por creador (UUID)"),
    my_competitions: bool | None = Query(
        None,
        description="Si es True, devuelve competiciones del usuario. Si es False, las excluye.",
    ),
    search_name: str | None = Query(None, description="Buscar por nombre de competición"),
    search_creator: str | None = Query(None, description="Buscar por nombre del creador"),
):
    """Endpoint para listar competiciones con filtros opcionales."""
    try:
        current_user_id = UserId(str(current_user.id))
        sanitized_creator_id = _sanitize_creator_id(creator_id)

        async with uow, user_uow:
            if my_competitions is True:
                competitions = await _get_user_competitions(
                    uow,
                    use_case,
                    current_user_id,
                    status_filter,
                    search_name,
                    search_creator,
                )
            elif my_competitions is False:
                competitions = await _get_all_competitions(
                    use_case,
                    status_filter,
                    sanitized_creator_id,
                    search_name,
                    search_creator,
                    viewer_id=str(current_user_id.value),
                    is_admin=current_user.is_admin,
                )
                competitions = await _exclude_user_competitions(competitions, current_user_id, uow)
            else:
                competitions = await _get_all_competitions(
                    use_case,
                    status_filter,
                    sanitized_creator_id,
                    search_name,
                    search_creator,
                    viewer_id=str(current_user_id.value),
                    is_admin=current_user.is_admin,
                )

            result = await _map_competitions_to_dtos(
                competitions, current_user_id, uow, user_uow, is_admin=current_user.is_admin
            )

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


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
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    get_competition_uc: GetCompetitionUseCase = Depends(get_get_competition_use_case),
    delete_uc: DeleteCompetitionUseCase = Depends(get_delete_competition_use_case),
):
    """Endpoint para obtener el detalle de una competición."""
    try:
        current_user_id = UserId(str(current_user.id))
        competition_vo_id = CompetitionId(competition_id)

        # Por el caso de uso y no por el repositorio: mirar una competicion
        # programada despues de su hora es lo que abre sus inscripciones, y no
        # hay ningun proceso de fondo que lo haga por su cuenta (BE #319)
        try:
            await get_competition_uc.execute(competition_vo_id)
        except CompetitionNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Competition {competition_vo_id.value} not found",
            ) from e

        async with uow, user_uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)

            if not competition:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Competition {competition_vo_id.value} not found",
                )

            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow, is_admin=current_user.is_admin
            )

        # Solo aquí y no en el mapper, que usan también los listados: saberlo
        # exige recorrer lo jugado. La regla es la misma que aplica el borrado,
        # no una copia (BE #347). Fuera del bloque de arriba: el caso de uso abre
        # su propia unidad de trabajo
        dto.can_delete = await delete_uc.puede_borrar(
            competition_vo_id, current_user_id, is_admin=current_user.is_admin
        )
        # Igual, solo en la ficha: con él elige el botón de capitanes (FE #692)
        dto.teams_assigned = await get_competition_uc.tiene_equipos(competition_vo_id)
        return dto

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.put(
    "/{competition_id}",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar competición",
    description="Actualiza una competición mientras las inscripciones siguen abiertas (DRAFT o ACTIVE). Creador o administrador.",
    tags=["Competitions"],
)
@limiter.limit("10/hour")
async def update_competition(
    request: Request,  # noqa: ARG001 - Requerido por SlowAPI limiter
    competition_id: UUID,
    competition_data: UpdateCompetitionRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: UpdateCompetitionUseCase = Depends(get_update_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
):
    """Endpoint para actualizar una competición."""
    try:
        current_user_id = UserId(str(current_user.id))
        competition_vo_id = CompetitionId(competition_id)

        await use_case.execute(competition_vo_id, competition_data, current_user_id, is_admin=current_user.is_admin)

        async with uow, user_uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)

            if not competition:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Competition {competition_vo_id.value} not found after update",
                )

            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow, is_admin=current_user.is_admin
            )

        return dto

    except CompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotCompetitionCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    # Los tres errores de país se nombran uno a uno porque NINGUNO hereda de
    # ValueError, y todos llegan hasta aquí desde que el PUT acepta `countries`:
    # el país que no existe o no es adyacente (InvalidCountryError), el código de
    # dos caracteres pero mal formado como "1a" (InvalidCountryCodeError) y el
    # país repetido, que el DTO deja pasar y rechaza la Location
    # (InvalidLocationError). Sin nombrarlos, cada uno sale como un 500.
    except (
        CompetitionNotEditableError,
        InvalidCountryError,
        InvalidCountryCodeError,
        InvalidLocationError,
        ValueError,
    ) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete(
    "/{competition_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar competición",
    description=(
        "Elimina físicamente una competición, con todo lo que cuelga de ella. "
        "Solo el creador o un administrador, y solo si se cumplen DOS cosas: el "
        "estado lo permite (todos menos IN_PROGRESS y COMPLETED) y no hay nada "
        "jugado: ningún partido terminado, con walkover o concedido, ni un hoyo "
        "anotado. La segunda no se deduce del estado: reabrir las inscripciones "
        "devuelve a ACTIVE un torneo ya jugado sin borrar sus partidos. El "
        "calendario sin jugar y los equipos sorteados no lo impiden, y se van "
        "con ella. Si no se cumple, 400."
    ),
    tags=["Competitions"],
)
@limiter.limit("10/hour")
async def delete_competition(
    request: Request,  # noqa: ARG001 - Requerido por SlowAPI limiter
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: DeleteCompetitionUseCase = Depends(get_delete_competition_use_case),
):
    """Endpoint para eliminar físicamente una competición."""
    try:
        current_user_id = UserId(str(current_user.id))

        request_dto = DeleteCompetitionRequestDTO(competition_id=competition_id)

        await use_case.execute(request_dto, current_user_id, is_admin=current_user.is_admin)

        return

    except CompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotCompetitionCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except (CompetitionNotDeletableError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
