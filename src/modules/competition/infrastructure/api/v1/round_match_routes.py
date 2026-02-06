"""
Round & Match Routes - API REST Layer (Infrastructure).

Endpoints FastAPI para gestión de rondas, partidos y equipos
del módulo Competition siguiendo Clean Architecture.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.config.dependencies import (
    get_assign_teams_use_case,
    get_configure_schedule_use_case,
    get_create_round_use_case,
    get_current_user,
    get_declare_walkover_use_case,
    get_delete_round_use_case,
    get_generate_matches_use_case,
    get_get_match_detail_use_case,
    get_get_schedule_use_case,
    get_reassign_match_players_use_case,
    get_update_match_status_use_case,
    get_update_round_use_case,
)
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.round_match_dto import (
    AssignTeamsBodyDTO,
    AssignTeamsRequestDTO,
    AssignTeamsResponseDTO,
    ConfigureScheduleBodyDTO,
    ConfigureScheduleRequestDTO,
    ConfigureScheduleResponseDTO,
    CreateRoundBodyDTO,
    CreateRoundRequestDTO,
    CreateRoundResponseDTO,
    DeclareWalkoverBodyDTO,
    DeclareWalkoverRequestDTO,
    DeclareWalkoverResponseDTO,
    DeleteRoundRequestDTO,
    DeleteRoundResponseDTO,
    GenerateMatchesBodyDTO,
    GenerateMatchesRequestDTO,
    GenerateMatchesResponseDTO,
    GetMatchDetailRequestDTO,
    GetMatchDetailResponseDTO,
    GetScheduleRequestDTO,
    GetScheduleResponseDTO,
    ReassignMatchPlayersBodyDTO,
    ReassignMatchPlayersRequestDTO,
    ReassignMatchPlayersResponseDTO,
    UpdateMatchStatusBodyDTO,
    UpdateMatchStatusRequestDTO,
    UpdateMatchStatusResponseDTO,
    UpdateRoundBodyDTO,
    UpdateRoundRequestDTO,
    UpdateRoundResponseDTO,
)
from src.modules.competition.application.use_cases.assign_teams_use_case import (
    AssignTeamsUseCase,
    CompetitionNotClosedError as AssignTeamsNotClosedError,
    CompetitionNotFoundError as AssignTeamsNotFoundError,
    InsufficientPlayersError as AssignTeamsInsufficientError,
    NotCompetitionCreatorError as AssignTeamsNotCreatorError,
    OddPlayersError,
    PlayerNotEnrolledError,
)
from src.modules.competition.application.use_cases.configure_schedule_use_case import (
    CompetitionNotClosedError as ConfigSchedNotClosedError,
    CompetitionNotFoundError as ConfigSchedNotFoundError,
    ConfigureScheduleUseCase,
    NoGolfCoursesError,
    NotCompetitionCreatorError as ConfigSchedNotCreatorError,
)
from src.modules.competition.application.use_cases.create_round_use_case import (
    CompetitionNotClosedError as CreateRoundNotClosedError,
    CompetitionNotFoundError as CreateRoundNotFoundError,
    CreateRoundUseCase,
    DateOutOfRangeError,
    DuplicateSessionError as CreateRoundDuplicateSessionError,
    GolfCourseNotInCompetitionError as CreateRoundGCNotInCompError,
    NotCompetitionCreatorError as CreateRoundNotCreatorError,
)
from src.modules.competition.application.use_cases.declare_walkover_use_case import (
    CompetitionNotInProgressError as WalkoverNotInProgressError,
    DeclareWalkoverUseCase,
    InvalidWalkoverError,
    MatchNotFoundError as WalkoverMatchNotFoundError,
    NotCompetitionCreatorError as WalkoverNotCreatorError,
)
from src.modules.competition.application.use_cases.delete_round_use_case import (
    CompetitionNotClosedError as DeleteRoundNotClosedError,
    DeleteRoundUseCase,
    NotCompetitionCreatorError as DeleteRoundNotCreatorError,
    RoundNotFoundError as DeleteRoundNotFoundError,
    RoundNotModifiableError as DeleteRoundNotModifiableError,
)
from src.modules.competition.application.use_cases.generate_matches_use_case import (
    CompetitionNotClosedError as GenMatchesNotClosedError,
    GenerateMatchesUseCase,
    InsufficientPlayersError as GenMatchesInsufficientError,
    NotCompetitionCreatorError as GenMatchesNotCreatorError,
    NoTeamAssignmentError,
    RoundNotFoundError as GenMatchesRoundNotFoundError,
    RoundNotPendingMatchesError,
    TeeCategoryNotFoundError,
)
from src.modules.competition.application.use_cases.get_match_detail_use_case import (
    GetMatchDetailUseCase,
    MatchNotFoundError as GetMatchNotFoundError,
)
from src.modules.competition.application.use_cases.get_schedule_use_case import (
    CompetitionNotFoundError as GetScheduleNotFoundError,
    GetScheduleUseCase,
)
from src.modules.competition.application.use_cases.reassign_match_players_use_case import (
    MatchNotFoundError as ReassignMatchNotFoundError,
    MatchNotScheduledError,
    NotCompetitionCreatorError as ReassignNotCreatorError,
    PlayerNotInTeamError,
    ReassignMatchPlayersUseCase,
)
from src.modules.competition.application.use_cases.update_match_status_use_case import (
    CompetitionNotInProgressError as StatusNotInProgressError,
    InvalidActionError,
    MatchNotFoundError as StatusMatchNotFoundError,
    NotCompetitionCreatorError as StatusNotCreatorError,
    UpdateMatchStatusUseCase,
)
from src.modules.competition.application.use_cases.update_round_use_case import (
    CompetitionNotClosedError as UpdateRoundNotClosedError,
    DuplicateSessionError as UpdateRoundDuplicateSessionError,
    GolfCourseNotInCompetitionError as UpdateRoundGCNotInCompError,
    NotCompetitionCreatorError as UpdateRoundNotCreatorError,
    RoundNotFoundError as UpdateRoundNotFoundError,
    RoundNotModifiableError as UpdateRoundNotModifiableError,
    UpdateRoundUseCase,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)

router = APIRouter()


# ======================================================================================
# ROUNDS CRUD ENDPOINTS
# ======================================================================================


@router.post(
    "/{competition_id}/rounds",
    response_model=CreateRoundResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear ronda",
    tags=["Competitions - Rounds"],
)
@limiter.limit("10/minute")
async def create_round(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    body: CreateRoundBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CreateRoundUseCase = Depends(get_create_round_use_case),
):
    """
    Crea una nueva ronda/sesión de competición.

    **Restricciones:**
    - Solo el creador puede crear rondas
    - La competición debe estar en estado CLOSED
    - El campo de golf debe estar asociado a la competición
    - No puede haber sesión duplicada (misma fecha + tipo de sesión)

    **Returns:**
    - 201: Ronda creada exitosamente
    - 400: Estado inválido, sesión duplicada, fecha fuera de rango, o campo no asociado
    - 403: Usuario no es el creador
    - 404: Competición no encontrada
    """
    try:
        current_user_id = UserId(current_user.id)
        request_dto = CreateRoundRequestDTO(
            competition_id=competition_id,
            golf_course_id=body.golf_course_id,
            round_date=body.round_date,
            session_type=body.session_type,
            match_format=body.match_format,
            handicap_mode=body.handicap_mode,
            allowance_percentage=body.allowance_percentage,
        )
        return await use_case.execute(request_dto, current_user_id)

    except CreateRoundNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except CreateRoundNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (
        CreateRoundNotClosedError,
        CreateRoundGCNotInCompError,
        CreateRoundDuplicateSessionError,
        DateOutOfRangeError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.put(
    "/rounds/{round_id}",
    response_model=UpdateRoundResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar ronda",
    tags=["Competitions - Rounds"],
)
@limiter.limit("10/minute")
async def update_round(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    round_id: UUID,
    body: UpdateRoundBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: UpdateRoundUseCase = Depends(get_update_round_use_case),
):
    """
    Actualiza una ronda existente (campos opcionales).

    **Restricciones:**
    - Solo el creador puede modificar rondas
    - La ronda debe estar en estado modificable (PENDING_TEAMS o PENDING_MATCHES)
    - La competición debe estar en estado CLOSED

    **Returns:**
    - 200: Ronda actualizada
    - 400: Estado no modificable, sesión duplicada, o campo no asociado
    - 403: Usuario no es el creador
    - 404: Ronda no encontrada
    """
    try:
        current_user_id = UserId(current_user.id)
        request_dto = UpdateRoundRequestDTO(
            round_id=round_id,
            round_date=body.round_date,
            session_type=body.session_type,
            golf_course_id=body.golf_course_id,
            match_format=body.match_format,
            handicap_mode=body.handicap_mode,
            allowance_percentage=body.allowance_percentage,
            clear_allowance=body.clear_allowance,
        )
        return await use_case.execute(request_dto, current_user_id)

    except UpdateRoundNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except UpdateRoundNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (
        UpdateRoundNotClosedError,
        UpdateRoundNotModifiableError,
        UpdateRoundGCNotInCompError,
        UpdateRoundDuplicateSessionError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete(
    "/rounds/{round_id}",
    response_model=DeleteRoundResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Eliminar ronda",
    tags=["Competitions - Rounds"],
)
@limiter.limit("10/minute")
async def delete_round(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    round_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: DeleteRoundUseCase = Depends(get_delete_round_use_case),
):
    """
    Elimina una ronda y sus partidos asociados.

    **Restricciones:**
    - Solo el creador puede eliminar rondas
    - La ronda debe estar en estado modificable (PENDING_TEAMS o PENDING_MATCHES)
    - La competición debe estar en estado CLOSED

    **Returns:**
    - 200: Ronda eliminada
    - 400: Estado no modificable
    - 403: Usuario no es el creador
    - 404: Ronda no encontrada
    """
    try:
        current_user_id = UserId(current_user.id)
        request_dto = DeleteRoundRequestDTO(round_id=round_id)
        return await use_case.execute(request_dto, current_user_id)

    except DeleteRoundNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except DeleteRoundNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (
        DeleteRoundNotClosedError,
        DeleteRoundNotModifiableError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/{competition_id}/schedule",
    response_model=GetScheduleResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Obtener schedule de competición",
    tags=["Competitions - Rounds"],
)
@limiter.limit("20/minute")
async def get_schedule(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),  # noqa: ARG001
    use_case: GetScheduleUseCase = Depends(get_get_schedule_use_case),
):
    """
    Obtiene el schedule completo de una competición con rondas agrupadas por día.

    **Returns:**
    - 200: Schedule con días, rondas, partidos y asignación de equipos
    - 404: Competición no encontrada
    """
    try:
        request_dto = GetScheduleRequestDTO(competition_id=competition_id)
        return await use_case.execute(request_dto)

    except GetScheduleNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


# ======================================================================================
# MATCH ENDPOINTS
# ======================================================================================


@router.get(
    "/matches/{match_id}",
    response_model=GetMatchDetailResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de partido",
    tags=["Competitions - Matches"],
)
@limiter.limit("20/minute")
async def get_match_detail(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    match_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),  # noqa: ARG001
    use_case: GetMatchDetailUseCase = Depends(get_get_match_detail_use_case),
):
    """
    Obtiene el detalle completo de un partido.

    **Returns:**
    - 200: Detalle del partido con jugadores, handicaps y resultado
    - 404: Partido no encontrado
    """
    try:
        request_dto = GetMatchDetailRequestDTO(match_id=match_id)
        return await use_case.execute(request_dto)

    except GetMatchNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.put(
    "/matches/{match_id}/status",
    response_model=UpdateMatchStatusResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar estado de partido",
    tags=["Competitions - Matches"],
)
@limiter.limit("10/minute")
async def update_match_status(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    match_id: UUID,
    body: UpdateMatchStatusBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: UpdateMatchStatusUseCase = Depends(get_update_match_status_use_case),
):
    """
    Actualiza el estado de un partido (START o COMPLETE).

    **Restricciones:**
    - Solo el creador puede cambiar estados
    - La competición debe estar IN_PROGRESS
    - Acciones válidas: START (SCHEDULED→IN_PROGRESS), COMPLETE (IN_PROGRESS→COMPLETED)

    **Returns:**
    - 200: Estado actualizado
    - 400: Acción inválida o competición no en progreso
    - 403: Usuario no es el creador
    - 404: Partido no encontrado
    """
    try:
        current_user_id = UserId(current_user.id)
        request_dto = UpdateMatchStatusRequestDTO(
            match_id=match_id,
            action=body.action,
            result=body.result,
        )
        return await use_case.execute(request_dto, current_user_id)

    except StatusMatchNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except StatusNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (
        StatusNotInProgressError,
        InvalidActionError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/matches/{match_id}/walkover",
    response_model=DeclareWalkoverResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Declarar walkover",
    tags=["Competitions - Matches"],
)
@limiter.limit("10/minute")
async def declare_walkover(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    match_id: UUID,
    body: DeclareWalkoverBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: DeclareWalkoverUseCase = Depends(get_declare_walkover_use_case),
):
    """
    Declara un walkover (victoria por incomparecencia) en un partido.

    **Restricciones:**
    - Solo el creador puede declarar walkovers
    - La competición debe estar IN_PROGRESS
    - El partido debe estar en estado válido para walkover

    **Returns:**
    - 200: Walkover declarado
    - 400: Walkover inválido o competición no en progreso
    - 403: Usuario no es el creador
    - 404: Partido no encontrado
    """
    try:
        current_user_id = UserId(current_user.id)
        request_dto = DeclareWalkoverRequestDTO(
            match_id=match_id,
            winning_team=body.winning_team,
            reason=body.reason,
        )
        return await use_case.execute(request_dto, current_user_id)

    except WalkoverMatchNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except WalkoverNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (
        WalkoverNotInProgressError,
        InvalidWalkoverError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.put(
    "/matches/{match_id}/players",
    response_model=ReassignMatchPlayersResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Reasignar jugadores de partido",
    tags=["Competitions - Matches"],
)
@limiter.limit("10/minute")
async def reassign_match_players(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    match_id: UUID,
    body: ReassignMatchPlayersBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ReassignMatchPlayersUseCase = Depends(get_reassign_match_players_use_case),
):
    """
    Reasigna los jugadores de un partido (recalcula handicaps).

    **Restricciones:**
    - Solo el creador puede reasignar jugadores
    - El partido debe estar en estado SCHEDULED
    - Los jugadores deben pertenecer a los equipos asignados

    **Returns:**
    - 200: Jugadores reasignados con handicaps recalculados
    - 400: Partido no scheduled o jugadores no válidos
    - 403: Usuario no es el creador
    - 404: Partido no encontrado
    """
    try:
        current_user_id = UserId(current_user.id)
        request_dto = ReassignMatchPlayersRequestDTO(
            match_id=match_id,
            team_a_player_ids=body.team_a_player_ids,
            team_b_player_ids=body.team_b_player_ids,
        )
        return await use_case.execute(request_dto, current_user_id)

    except ReassignMatchNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ReassignNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (
        MatchNotScheduledError,
        PlayerNotInTeamError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logging.exception("Error inesperado en reassign_match_players: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


# ======================================================================================
# TEAMS & GENERATION ENDPOINTS
# ======================================================================================


@router.post(
    "/{competition_id}/teams",
    response_model=AssignTeamsResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Asignar equipos",
    tags=["Competitions - Teams"],
)
@limiter.limit("10/minute")
async def assign_teams(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    body: AssignTeamsBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: AssignTeamsUseCase = Depends(get_assign_teams_use_case),
):
    """
    Asigna equipos para la competición (automático con snake draft o manual).

    **Restricciones:**
    - Solo el creador puede asignar equipos
    - La competición debe estar en estado CLOSED
    - Debe haber suficientes jugadores inscritos (mínimo 2)
    - En modo MANUAL, los equipos deben estar balanceados

    **Returns:**
    - 201: Equipos asignados
    - 400: Estado inválido, jugadores insuficientes, o equipos desequilibrados
    - 403: Usuario no es el creador
    - 404: Competición no encontrada
    """
    try:
        current_user_id = UserId(current_user.id)
        request_dto = AssignTeamsRequestDTO(
            competition_id=competition_id,
            mode=body.mode,
            team_a_player_ids=body.team_a_player_ids,
            team_b_player_ids=body.team_b_player_ids,
        )
        return await use_case.execute(request_dto, current_user_id)

    except AssignTeamsNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except AssignTeamsNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (
        AssignTeamsNotClosedError,
        AssignTeamsInsufficientError,
        OddPlayersError,
        PlayerNotEnrolledError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/rounds/{round_id}/matches/generate",
    response_model=GenerateMatchesResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Generar partidos",
    tags=["Competitions - Matches"],
)
@limiter.limit("10/minute")
async def generate_matches(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    round_id: UUID,
    body: GenerateMatchesBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GenerateMatchesUseCase = Depends(get_generate_matches_use_case),
):
    """
    Genera partidos para una ronda basándose en los equipos asignados.

    **Restricciones:**
    - Solo el creador puede generar partidos
    - La ronda debe estar en estado PENDING_MATCHES
    - Debe existir asignación de equipos
    - La competición debe estar en estado CLOSED

    **Returns:**
    - 201: Partidos generados
    - 400: Estado inválido, sin equipos, o jugadores insuficientes
    - 404: Ronda no encontrada
    """
    try:
        current_user_id = UserId(current_user.id)
        request_dto = GenerateMatchesRequestDTO(
            round_id=round_id,
            manual_pairings=body.manual_pairings,
        )
        return await use_case.execute(request_dto, current_user_id)

    except GenMatchesRoundNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except GenMatchesNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (
        GenMatchesNotClosedError,
        RoundNotPendingMatchesError,
        NoTeamAssignmentError,
        GenMatchesInsufficientError,
        TeeCategoryNotFoundError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/{competition_id}/schedule/configure",
    response_model=ConfigureScheduleResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Configurar schedule",
    tags=["Competitions - Rounds"],
)
@limiter.limit("10/minute")
async def configure_schedule(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    body: ConfigureScheduleBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ConfigureScheduleUseCase = Depends(get_configure_schedule_use_case),
):
    """
    Configura el schedule de la competición (automático o manual).

    **Restricciones:**
    - Solo el creador puede configurar el schedule
    - La competición debe estar en estado CLOSED
    - Debe tener al menos un campo de golf asociado (modo AUTO)

    **Returns:**
    - 200: Schedule configurado
    - 400: Estado inválido o sin campos de golf
    - 403: Usuario no es el creador
    - 404: Competición no encontrada
    """
    try:
        current_user_id = UserId(current_user.id)
        request_dto = ConfigureScheduleRequestDTO(
            competition_id=competition_id,
            mode=body.mode,
            total_sessions=body.total_sessions,
            sessions_per_day=body.sessions_per_day,
        )
        return await use_case.execute(request_dto, current_user_id)

    except ConfigSchedNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ConfigSchedNotCreatorError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (
        ConfigSchedNotClosedError,
        NoGolfCoursesError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
