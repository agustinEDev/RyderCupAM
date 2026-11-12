"""Competition CRUD Routes - Create, Read, Update, Delete endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from src.config.dependencies import (
    get_competition_summary_use_case,
    get_create_competition_use_case,
    get_current_user,
    get_delete_competition_use_case,
    get_get_competition_use_case,
    get_handicap_update_status_use_case,
    get_list_competitions_use_case,
    get_update_competition_use_case,
    get_update_stroke_play_settings_use_case,
    get_ventana_de_actualizacion_use_case,
    get_vista_de_competicion_use_case,
)
from src.config.rate_limit import limite_de_lo_publico, limiter
from src.modules.competition.application.dto.competition_dto import (
    CompetitionResponseDTO,
    CompetitionSummaryDTO,
    CreateCompetitionRequestDTO,
    CreateCompetitionResponseDTO,
    DeleteCompetitionRequestDTO,
    GetCompetitionSummaryRequestDTO,
    StrokePlaySettingsDTO,
    StrokePlaySettingsResponseDTO,
    UpdateCompetitionRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
)
from src.modules.competition.application.use_cases.actualizar_handicaps_use_case import (
    VentanaDeActualizacionUseCase,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.delete_competition_use_case import (
    CompetitionNotDeletableError,
    DeleteCompetitionUseCase,
)
from src.modules.competition.application.use_cases.get_competition_summary_use_case import (
    GetCompetitionSummaryUseCase,
)
from src.modules.competition.application.use_cases.get_competition_use_case import (
    GetCompetitionUseCase,
)
from src.modules.competition.application.use_cases.get_handicap_update_status_use_case import (
    GetHandicapUpdateStatusUseCase,
)
from src.modules.competition.application.use_cases.list_competitions_use_case import (
    ListCompetitionsUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    CompetitionNotEditableError,
    DatesLeaveSessionsOutError,
    UpdateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.update_stroke_play_settings_use_case import (
    UpdateStrokePlaySettingsUseCase,
)
from src.modules.competition.application.use_cases.vista_de_competicion_use_case import (
    VistaDeCompeticionUseCase,
)
from src.modules.competition.domain.entities.competition import CompetitionStateError
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.api.v1.correo_de_quien_mira import correo_de_quien_mira
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)

router = APIRouter()


# ======================================================================================
# HELPER FUNCTIONS (for list endpoint)
# ======================================================================================


def _sanitize_creator_id(creator_id: str | None) -> str | None:
    if creator_id and creator_id not in ("undefined", "null", ""):
        return creator_id
    return None


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
    vista: VistaDeCompeticionUseCase = Depends(get_vista_de_competicion_use_case),
):
    """Endpoint para crear una nueva competición."""
    try:
        creator_id = UserId(str(current_user.id))

        response = await use_case.execute(competition_data, creator_id)

        try:
            enriched_dto = await vista.de(CompetitionId(response.id), creator_id)
        except CompetitionNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Competition created but not found",
            ) from e

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
            enrollment_opens_days_before=enriched_dto.enrollment_opens_days_before,
            visibility=enriched_dto.visibility,
            setup_mode=enriched_dto.setup_mode,
            team_1_name=enriched_dto.team_1_name,
            team_2_name=enriched_dto.team_2_name,
            tournament_type=enriched_dto.tournament_type,
            modality=enriched_dto.modality,
            stroke_play=enriched_dto.stroke_play,
            is_creator=True,
            enrolled_count=0,
            created_at=enriched_dto.created_at,
            updated_at=enriched_dto.updated_at,
        )

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
    vista: VistaDeCompeticionUseCase = Depends(get_vista_de_competicion_use_case),
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
        quien = UserId(str(current_user.id))
        correo = correo_de_quien_mira(current_user)

        if my_competitions is True:
            competitions = await use_case.mis_competiciones(
                quien,
                status_filter,
                search_name=search_name,
                search_creator=search_creator,
                viewer_email=correo,
            )
        elif my_competitions is False:
            competitions = await use_case.las_de_los_demas(
                quien,
                status_filter,
                creator_id=_sanitize_creator_id(creator_id),
                search_name=search_name,
                search_creator=search_creator,
                is_admin=current_user.is_admin,
                viewer_email=correo,
            )
        else:
            competitions = await use_case.listar(
                status_filter,
                creator_id=_sanitize_creator_id(creator_id),
                search_name=search_name,
                search_creator=search_creator,
                viewer_id=str(quien.value),
                is_admin=current_user.is_admin,
                viewer_email=correo,
            )

        return await vista.de_varias(competitions, quien, es_admin=current_user.is_admin)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/{competition_id}/summary",
    response_model=CompetitionSummaryDTO,
    status_code=status.HTTP_200_OK,
    summary="Resumen público de una competición",
    description=(
        "Sin sesión: nombre, tipo, estado, visibilidad y fechas, para la página de su "
        "clasificación (release social 3). También de una privada."
    ),
    tags=["Competitions"],
)
@limiter.limit(limite_de_lo_publico)
async def get_competition_summary(
    request: Request,  # noqa: ARG001 - Requerido por SlowAPI limiter
    competition_id: UUID,
    use_case: GetCompetitionSummaryUseCase = Depends(get_competition_summary_use_case),
):
    """
    200 con el resumen; 404 si no existe. No mira la sesión: con una caducada o sin
    Términos aceptados sale igual (code-review). El límite sí cuenta por usuario si
    hay un token válido (`get_rate_limit_key` lo verifica por su cuenta).
    """
    try:
        return await use_case.execute(
            GetCompetitionSummaryRequestDTO(competition_id=competition_id)
        )
    except CompetitionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Competition {competition_id} not found"
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
    get_competition_uc: GetCompetitionUseCase = Depends(get_get_competition_use_case),
    vista: VistaDeCompeticionUseCase = Depends(get_vista_de_competicion_use_case),
    delete_uc: DeleteCompetitionUseCase = Depends(get_delete_competition_use_case),
    handicaps_uc: GetHandicapUpdateStatusUseCase = Depends(get_handicap_update_status_use_case),
    ventana_uc: VentanaDeActualizacionUseCase = Depends(get_ventana_de_actualizacion_use_case),
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
            # Con la invitación pendiente de quien mira (para aceptarla desde la
            # ficha) y lo que ve de los inscritos
            dto = await vista.ficha(
                competition_vo_id,
                current_user_id,
                es_admin=current_user.is_admin,
                email=correo_de_quien_mira(current_user),
            )
        except CompetitionNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Competition {competition_vo_id.value} not found",
            ) from e

        # Solo aquí y no en el mapper, que usan también los listados: saberlo
        # exige recorrer lo jugado. La regla es la misma que aplica el borrado,
        # no una copia (BE #347). El caso de uso abre su propia unidad de trabajo
        dto.can_delete = await delete_uc.puede_borrar(
            competition_vo_id, current_user_id, is_admin=current_user.is_admin
        )
        # Igual, solo en la ficha: con él elige el botón de capitanes (FE #692)
        dto.teams_assigned = await get_competition_uc.tiene_equipos(competition_vo_id)
        # Cómo se repartieron DE VERDAD: la competición guarda el modo con el
        # que nació, y así unos equipos salidos del draft se contaban como
        # repartidos a mano
        dto.actual_team_assignment = await get_competition_uc.reparto_real(competition_vo_id)
        # Solo para quien organiza: cómo va la actualización de hándicaps (#251).
        # A los demás ni se les pregunta: es la ficha, la que más se pide
        if dto.is_creator or current_user.is_admin:
            dto.handicap_update = await handicaps_uc.execute(
                competition_vo_id, current_user_id, is_admin=current_user.is_admin
            )
            dto.handicap_update_window = await ventana_uc.execute(
                competition_vo_id, current_user_id, is_admin=current_user.is_admin
            )
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
# Por minuto, como el resto de modificaciones: quien monta su torneo retoca
# mucho, y cada rechazo de la API también cuenta (Agustín, 4 oct 2026)
@limiter.limit("10/minute")
async def update_competition(
    request: Request,  # noqa: ARG001 - Requerido por SlowAPI limiter
    competition_id: UUID,
    competition_data: UpdateCompetitionRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: UpdateCompetitionUseCase = Depends(get_update_competition_use_case),
    vista: VistaDeCompeticionUseCase = Depends(get_vista_de_competicion_use_case),
):
    """Endpoint para actualizar una competición."""
    try:
        current_user_id = UserId(str(current_user.id))
        competition_vo_id = CompetitionId(competition_id)

        await use_case.execute(
            competition_vo_id, competition_data, current_user_id, is_admin=current_user.is_admin
        )

        return await vista.de(competition_vo_id, current_user_id, es_admin=current_user.is_admin)

    # Los tres errores de país se nombran uno a uno porque NINGUNO hereda de
    # ValueError, y todos llegan hasta aquí desde que el PUT acepta `countries`:
    # el país que no existe o no es adyacente (InvalidCountryError), el código de
    # dos caracteres pero mal formado como "1a" (InvalidCountryCodeError) y el
    # país repetido, que el DTO deja pasar y rechaza la Location
    # (InvalidLocationError). Sin nombrarlos, cada uno sale como un 500.
    except DatesLeaveSessionsOutError as e:
        # Cuáles, y no solo que alguna (#710). En claves: la pantalla escribe la
        # fecha y la franja en su idioma (decidido el 24 sep, BE #360)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": (
                    "No se pueden mover las fechas: alguna sesión quedaría fuera del torneo. "
                    "Cambia o borra antes esas sesiones."
                ),
                "error_code": "DATES_LEAVE_SESSIONS_OUT",
                "sessions_outside": [
                    {"id": str(id_), "round_date": dia.isoformat(), "session_type": franja}
                    for id_, dia, franja in e.sesiones
                ],
            },
        )
    except (CompetitionNotEditableError, ValueError) as e:
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

    except (CompetitionNotDeletableError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.patch(
    "/{competition_id}/stroke-play",
    response_model=StrokePlaySettingsResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Cambiar los ajustes del stroke play",
    description=(
        "Categorías, jornadas por jugador y regla de la general de un Stableford o un "
        "Medal (#251). Lo que no llega no se toca; una lista de límites vacía quita las "
        "categorías. Solo el creador o un admin, y hasta que la competición empieza "
        "(DRAFT, ACTIVE o CLOSED). En una Ryder Cup es un 400."
    ),
)
@limiter.limit("10/minute")
async def update_stroke_play_settings(
    request: Request,  # noqa: ARG001 - Requerido por SlowAPI limiter
    competition_id: UUID,
    ajustes: StrokePlaySettingsDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: UpdateStrokePlaySettingsUseCase = Depends(get_update_stroke_play_settings_use_case),
):
    """Cambia los ajustes del stroke play de una competición."""
    try:
        return await use_case.execute(
            competition_id,
            ajustes,
            UserId(str(current_user.id)),
            is_admin=current_user.is_admin,
        )
    except (CompetitionStateError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
