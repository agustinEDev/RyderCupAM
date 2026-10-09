"""
Rutas: anotar en las partidas de stroke play (#251, PR 5).

Bajo `/api/v1/competitions`. El cuerpo y los dos códigos que la cola sin conexión
del móvil ya entiende (`SCORING_NOT_OPEN_YET`, que se guarda y reintenta, y
`NOT_YOUR_MARKED_PLAYER`) son los de la Ryder. Los textos, fijos por clave: la
respuesta nunca lleva el de la excepción (CodeQL).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.config.dependencies import (
    get_anotar_hoyo_de_partida_use_case,
    get_current_user,
    get_ver_anotacion_de_partida_use_case,
)
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.partidas_dto import TeeGroupScoringViewDTO
from src.modules.competition.application.dto.scoring_dto import SubmitHoleScoreBodyDTO
from src.modules.competition.application.exceptions import (
    InvalidHoleNumberError,
    NotYourMarkedPlayerError,
    PartidaNotFoundError,
    ScoringNotOpenYetError,
)
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    AnotarHoyoDePartidaUseCase,
    NoEsDeLaPartidaError,
    PartidaNoAnotableError,
    SinMarcadorError,
)
from src.modules.competition.application.use_cases.ver_anotacion_de_partida_use_case import (
    VerAnotacionDePartidaUseCase,
)
from src.modules.competition.domain.entities.golpe_de_partida import RayaNoPermitidaError
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.value_objects.user_id import UserId

router = APIRouter()

# Error -> (estado HTTP, error_code, texto fijo)
_ERRORES: dict[type[Exception], tuple[int, str, str]] = {
    NotYourMarkedPlayerError: (
        status.HTTP_403_FORBIDDEN,
        NotYourMarkedPlayerError.error_code,
        NotYourMarkedPlayerError.message,
    ),
    NoEsDeLaPartidaError: (
        status.HTTP_403_FORBIDDEN,
        NoEsDeLaPartidaError.error_code,
        "No juegas esta partida.",
    ),
    SinMarcadorError: (
        status.HTTP_409_CONFLICT,
        SinMarcadorError.error_code,
        "En una partida de un jugador no hay a quién marcar: lo valida el organizador.",
    ),
    PartidaNoAnotableError: (
        status.HTTP_409_CONFLICT,
        PartidaNoAnotableError.error_code,
        "Esta partida no se puede anotar ahora.",
    ),
    RayaNoPermitidaError: (
        status.HTTP_400_BAD_REQUEST,
        "PICKED_UP_NOT_ALLOWED",
        "En Medal no se levanta bola: hay que acabar el hoyo.",
    ),
    InvalidHoleNumberError: (
        status.HTTP_400_BAD_REQUEST,
        "INVALID_HOLE",
        "El hoyo va del 1 al 18.",
    ),
}


def _respuesta(error: Exception) -> JSONResponse:
    if isinstance(error, ScoringNotOpenYetError):
        # Con la hora de apertura: la cola del móvil lo guarda y reintenta
        abre = error.opens_at.isoformat()
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": f"La anotación de esta franja abre a las {abre}",
                "error_code": ScoringNotOpenYetError.error_code,
                "scoring_opens_at": abre,
            },
        )
    for tipo, (status_code, codigo, detalle) in _ERRORES.items():
        if isinstance(error, tipo):
            return JSONResponse(
                status_code=status_code, content={"detail": detalle, "error_code": codigo}
            )
    raise error


_CON_CODIGO: tuple[type[Exception], ...] = (ScoringNotOpenYetError, *_ERRORES)
_NO_EXISTE = "No existe esa partida."


@router.post(
    "/groups/{group_id}/scores/holes/{hole}",
    response_model=TeeGroupScoringViewDTO,
    summary="Anotar un hoyo en una partida",
    description=(
        "Stableford o Medal. Tu golpe (`own_score`) y el de quien marcas (`marked_score`, "
        "con `marked_player_id`); omitir un campo no lo toca, y nulo es levantar bola (no "
        "en Medal). Abre para toda la franja a su primera salida."
    ),
    tags=["Competitions - Tee groups"],
)
@limiter.limit("30/minute")
async def score_tee_group_hole(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    group_id: UUID,
    hole: int,
    body: SubmitHoleScoreBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    anotar: AnotarHoyoDePartidaUseCase = Depends(get_anotar_hoyo_de_partida_use_case),
    ver: VerAnotacionDePartidaUseCase = Depends(get_ver_anotacion_de_partida_use_case),
):
    """200 con la partida; 4xx con `error_code` si no se puede."""
    quien = UserId(str(current_user.id))
    try:
        await anotar.execute(group_id, hole, body, quien)
        return await ver.execute(group_id, quien)
    except PartidaNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_EXISTE) from e
    except _CON_CODIGO as e:
        return _respuesta(e)


@router.get(
    "/groups/{group_id}/scoring-view",
    response_model=TeeGroupScoringViewDTO,
    summary="La partida para anotar",
    description="Cada jugador con sus 18 hoyos (su lado, el de su marcador) y lo validado.",
    tags=["Competitions - Tee groups"],
)
async def get_tee_group_scoring_view(
    group_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    ver: VerAnotacionDePartidaUseCase = Depends(get_ver_anotacion_de_partida_use_case),
):
    """200 con la partida; 404 si no existe."""
    try:
        return await ver.execute(group_id, UserId(str(current_user.id)))
    except PartidaNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_EXISTE) from e
