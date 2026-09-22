"""Rutas de la sala de draft (FE #653)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from src.config.dependencies import (
    get_current_user,
    get_draft_use_case,
    get_make_draft_pick_use_case,
    get_start_draft_use_case,
)
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.draft_dto import DraftStateDTO
from src.modules.competition.application.exceptions import (
    CompetitionNotClosedError,
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.get_draft_use_case import GetDraftUseCase
from src.modules.competition.application.use_cases.make_draft_pick_use_case import (
    MakeDraftPickUseCase,
)
from src.modules.competition.application.use_cases.start_draft_use_case import (
    DraftAlreadyStartedError,
    StartDraftUseCase,
)
from src.modules.competition.domain.entities.competition import CaptainMissingError
from src.modules.competition.domain.entities.draft import (
    DraftNotRunningError,
    NotYourTurnError,
    PlayerAlreadyPickedError,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.value_objects.user_id import UserId

router = APIRouter()


class DraftPickBodyDTO(BaseModel):
    """A quién elige el capitán."""

    player_id: UUID = Field(..., description="El jugador elegido.")


# Lo que es culpa de quien pide, no del servidor: una sala parada, un turno que
# no es suyo o un jugador que ya no está
_ERRORES_DE_LA_SALA = (
    CaptainMissingError,
    CompetitionNotClosedError,
    DraftAlreadyStartedError,
    DraftNotRunningError,
    PlayerAlreadyPickedError,
    ValueError,
)


@router.post(
    "/{competition_id}/draft",
    response_model=DraftStateDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Lanzar el sorteo y abrir la sala de draft",
    description=(
        "Sortea qué equipo elige primero y arranca su turno. Solo el organizador "
        "o un administrador, con las inscripciones ya cerradas, los dos capitanes "
        "nombrados y los equipos todavía sin repartir. Se lanza aunque falte un "
        "capitán por entrar: la aplicación elige por él cada vez que se agote su "
        "minuto."
    ),
    tags=["Competitions - Draft"],
)
@limiter.limit("10/minute")
async def start_draft(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: StartDraftUseCase = Depends(get_start_draft_use_case),
):
    """Abre la sala de draft (FE #653)."""
    try:
        return await use_case.execute(
            competition_id, UserId(str(current_user.id)), is_admin=current_user.is_admin
        )
    except CompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotCompetitionCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except _ERRORES_DE_LA_SALA as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/{competition_id}/draft",
    response_model=DraftStateDTO,
    status_code=status.HTTP_200_OK,
    summary="Mirar la sala de draft",
    description=(
        "La sala tal como está: de quién es el turno, cuánto le queda, los dos "
        "equipos llenándose y quién sigue disponible, con su nombre y su hándicap. "
        "Lleva la hora del servidor (`server_time`) para que el contador no dependa "
        "del reloj del móvil. Mirarla es además lo que resuelve los turnos que se "
        "hayan agotado. 404 si todavía no se ha lanzado el sorteo."
    ),
    tags=["Competitions - Draft"],
)
# 300/min: la sala la miran los doce a la vez, cada uno cada cinco segundos, y
# **comparten el mismo cubo** —uno por IP, y detras del proxy la IP es la misma
# para todos (ADR-038)—. Doce moviles son 144 peticiones por minuto, mas las
# recargas: con 120 la ceremonia entera se caia con 429, y con ella el turno
# agotado, que lo resuelve justo este GET
@limiter.limit("300/minute")
async def get_draft(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetDraftUseCase = Depends(get_draft_use_case),
):
    """Devuelve la sala de draft (FE #653)."""
    try:
        draft = await use_case.execute(competition_id, UserId(str(current_user.id)))
    except CompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todavía no se ha lanzado el sorteo de esta competición",
        )
    return draft


@router.post(
    "/{competition_id}/draft/picks",
    response_model=DraftStateDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Elegir a un jugador",
    description=(
        "Elige el capitán del equipo de turno, y nadie más. Si el minuto ya se "
        "había agotado, la aplicación habrá elegido por él y el turno será del "
        "otro: responde 409. Al elegir al último jugador, la sala termina y los "
        "equipos quedan repartidos."
    ),
    tags=["Competitions - Draft"],
)
@limiter.limit("60/minute")
async def make_draft_pick(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    body: DraftPickBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: MakeDraftPickUseCase = Depends(get_make_draft_pick_use_case),
):
    """Elige a un jugador para el equipo de turno (FE #653)."""
    try:
        return await use_case.execute(competition_id, UserId(str(current_user.id)), body.player_id)
    except CompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotYourTurnError as e:
        # 409 y no 403: no es que no pueda elegir nunca, es que ahora mismo no
        # le toca. La pantalla se vuelve a pintar y sigue
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except _ERRORES_DE_LA_SALA as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
