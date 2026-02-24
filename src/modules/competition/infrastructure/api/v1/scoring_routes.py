"""
Scoring Routes - API REST Layer (Infrastructure).

Endpoints FastAPI para scoring en vivo del modulo Competition.
5 endpoints: scoring-view, submit hole score, submit scorecard, leaderboard, concede.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.config.dependencies import (
    get_concede_match_use_case,
    get_current_user,
    get_get_leaderboard_use_case,
    get_get_scoring_view_use_case,
    get_submit_hole_score_use_case,
    get_submit_scorecard_use_case,
)
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.scoring_dto import (
    ConcedeMatchBodyDTO,
    LeaderboardResponseDTO,
    ScoringViewResponseDTO,
    SubmitHoleScoreBodyDTO,
    SubmitScorecardResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    InvalidHoleNumberError,
    MatchNotFoundError,
    MatchNotScoringError,
    NotMatchPlayerError,
    RoundNotFoundError,
    ScorecardAlreadySubmittedError,
    ScorecardNotReadyError,
)
from src.modules.competition.application.use_cases.concede_match_use_case import (
    ConcedeMatchUseCase,
)
from src.modules.competition.application.use_cases.get_leaderboard_use_case import (
    GetLeaderboardUseCase,
)
from src.modules.competition.application.use_cases.get_scoring_view_use_case import (
    GetScoringViewUseCase,
)
from src.modules.competition.application.use_cases.submit_hole_score_use_case import (
    SubmitHoleScoreUseCase,
)
from src.modules.competition.application.use_cases.submit_scorecard_use_case import (
    SubmitScorecardUseCase,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)

router = APIRouter()


# ======================================================================================
# SCORING ENDPOINTS
# ======================================================================================


@router.get(
    "/matches/{match_id}/scoring-view",
    response_model=ScoringViewResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Vista de scoring del partido",
    tags=["Competitions - Scoring"],
)
@limiter.limit("30/minute")
async def get_scoring_view(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    match_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),  # noqa: ARG001
    use_case: GetScoringViewUseCase = Depends(get_get_scoring_view_use_case),
):
    """
    Obtiene la vista completa de scoring de un partido.

    Incluye: scores por hoyo, validacion cruzada, standing, marker assignments.

    **Returns:**
    - 200: Vista de scoring completa
    - 404: Partido no encontrado
    """
    try:
        return await use_case.execute(str(match_id))

    except MatchNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except (RoundNotFoundError, CompetitionNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/matches/{match_id}/scores/holes/{hole_number}",
    response_model=ScoringViewResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Registrar score de hoyo",
    tags=["Competitions - Scoring"],
)
@limiter.limit("30/minute")
async def submit_hole_score(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    match_id: UUID,
    hole_number: int,
    body: SubmitHoleScoreBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: SubmitHoleScoreUseCase = Depends(get_submit_hole_score_use_case),
):
    """
    Registra el score de un jugador en un hoyo especifico.

    Incluye tanto own_score como marked_score (score que el marcador asigna al jugador marcado).
    Retorna la vista completa de scoring actualizada.

    **Restricciones:**
    - Solo jugadores del partido pueden registrar scores
    - El partido debe estar IN_PROGRESS
    - Hoyo debe estar entre 1-18
    - La tarjeta no debe haber sido entregada

    **Returns:**
    - 200: Score registrado, retorna scoring-view actualizado
    - 400: Hoyo invalido, tarjeta ya entregada
    - 403: No es jugador del partido
    - 404: Partido no encontrado
    - 409: Partido no en estado de scoring
    """
    try:
        current_user_id = UserId(current_user.id)
        return await use_case.execute(str(match_id), hole_number, body, current_user_id)

    except MatchNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except NotMatchPlayerError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except MatchNotScoringError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except (InvalidHoleNumberError, ScorecardAlreadySubmittedError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/matches/{match_id}/scorecard/submit",
    response_model=SubmitScorecardResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Entregar tarjeta de scores",
    tags=["Competitions - Scoring"],
)
@limiter.limit("10/minute")
async def submit_scorecard(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    match_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: SubmitScorecardUseCase = Depends(get_submit_scorecard_use_case),
):
    """
    Entrega la tarjeta de scores de un jugador.

    Valida que todos los hoyos jugados tengan validation_status MATCH.
    Si todos los jugadores entregan su tarjeta, el partido se completa automaticamente.

    **Restricciones:**
    - Solo jugadores del partido
    - El partido debe estar IN_PROGRESS
    - Todos los hoyos jugados deben tener validation_status MATCH
    - No se puede entregar dos veces

    **Returns:**
    - 200: Tarjeta entregada, retorna resultado si partido completado
    - 400: Hoyos sin validar, tarjeta ya entregada
    - 403: No es jugador del partido
    - 404: Partido no encontrado
    - 409: Partido no en estado de scoring
    """
    try:
        current_user_id = UserId(current_user.id)
        return await use_case.execute(str(match_id), current_user_id)

    except MatchNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except NotMatchPlayerError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except MatchNotScoringError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except (ScorecardNotReadyError, ScorecardAlreadySubmittedError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/{competition_id}/leaderboard",
    response_model=LeaderboardResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Leaderboard de la competicion",
    tags=["Competitions - Scoring"],
)
@limiter.limit("30/minute")
async def get_leaderboard(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),  # noqa: ARG001
    use_case: GetLeaderboardUseCase = Depends(get_get_leaderboard_use_case),
):
    """
    Obtiene el leaderboard completo de la competicion.

    Muestra todos los partidos con sus estados actuales, standings
    y los puntos totales Ryder Cup por equipo.

    **Auth:** JWT requerido, cualquier usuario autenticado.

    **Returns:**
    - 200: Leaderboard completo
    - 404: Competicion no encontrada
    """
    try:
        return await use_case.execute(str(competition_id))

    except CompetitionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


# ======================================================================================
# CONCEDE ENDPOINT
# ======================================================================================


@router.put(
    "/matches/{match_id}/concede",
    status_code=status.HTTP_200_OK,
    summary="Conceder partido",
    tags=["Competitions - Scoring"],
)
@limiter.limit("10/minute")
async def concede_match(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    match_id: UUID,
    body: ConcedeMatchBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ConcedeMatchUseCase = Depends(get_concede_match_use_case),
):
    """
    Concede un partido a favor del equipo contrario.

    **Auth:**
    - Jugadores del partido: solo pueden conceder SU propio equipo
    - Creator de la competicion: puede conceder cualquier equipo

    **Body:**
    - conceding_team: "A" o "B"
    - reason: string (opcional)

    **Returns:**
    - 200: Partido concedido
    - 400: Partido no en estado de scoring
    - 403: No es jugador ni creador
    - 404: Partido no encontrado
    """
    try:
        current_user_id = UserId(current_user.id)
        return await use_case.execute(
            str(match_id), current_user_id, body.conceding_team, body.reason
        )

    except MatchNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except NotMatchPlayerError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except MatchNotScoringError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except (RoundNotFoundError, CompetitionNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
