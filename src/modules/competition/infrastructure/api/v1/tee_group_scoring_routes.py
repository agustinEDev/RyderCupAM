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
    get_cerrar_franja_use_case,
    get_clasificacion_de_la_franja_use_case,
    get_clasificacion_general_use_case,
    get_clasificacion_scratch_use_case,
    get_corregir_hoyo_de_partida_use_case,
    get_current_user,
    get_entregar_tarjeta_de_partida_use_case,
    get_marcar_no_presentado_use_case,
    get_reabrir_tarjeta_use_case,
    get_retirarse_de_partida_use_case,
    get_ver_anotacion_de_partida_use_case,
)
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.partidas_dto import (
    CorrectHoleBodyDTO,
    StandingsResponseDTO,
    SubmitTeeGroupScoreBodyDTO,
    TeeGroupScoringViewDTO,
    TeeGroupsResponseDTO,
)
from src.modules.competition.application.exceptions import (
    InvalidHoleNumberError,
    NotCompetitionCreatorError,
    NotYourMarkedPlayerError,
    PartidaNotFoundError,
    PartidasError,
    RoundNotFoundError,
    ScoringNotOpenYetError,
)
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    AnotarHoyoDePartidaUseCase,
    NoEsDeLaPartidaError,
    PartidaNoAnotableError,
    SinMarcadorError,
)
from src.modules.competition.application.use_cases.clasificaciones_use_case import (
    ClasificacionDeLaFranjaUseCase,
    ClasificacionGeneralUseCase,
    ClasificacionScratchUseCase,
)
from src.modules.competition.application.use_cases.entregar_tarjeta_de_partida_use_case import (
    EntregarTarjetaDePartidaUseCase,
    RetirarseDePartidaUseCase,
    TarjetaIncompletaError,
)
from src.modules.competition.application.use_cases.organizador_de_partidas_use_case import (
    CerrarFranjaUseCase,
    CorregirHoyoDePartidaUseCase,
    MarcarNoPresentadoUseCase,
    ReabrirTarjetaUseCase,
)
from src.modules.competition.application.use_cases.ver_anotacion_de_partida_use_case import (
    VerAnotacionDePartidaUseCase,
)
from src.modules.competition.domain.entities.golpe_de_partida import RayaNoPermitidaError
from src.modules.competition.domain.entities.partida import (
    PartidaNoEmpezadaError,
    TarjetaCerradaError,
)
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
    PartidaNoEmpezadaError: (
        status.HTTP_409_CONFLICT,
        "GROUP_NOT_STARTED",
        "La partida aún no ha empezado.",
    ),
    TarjetaCerradaError: (
        status.HTTP_409_CONFLICT,
        "SCORECARD_ALREADY_SUBMITTED",
        "Esa tarjeta ya está cerrada.",
    ),
    NotCompetitionCreatorError: (
        status.HTTP_403_FORBIDDEN,
        "NOT_ORGANIZER",
        "Solo el organizador puede hacerlo.",
    ),
}


def _respuesta(error: Exception) -> JSONResponse:
    if isinstance(error, TarjetaIncompletaError):
        # Con los hoyos que faltan: la pantalla los señala (P4)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": "Quedan hoyos sin validar: jugador y marcador tienen que coincidir.",
                "error_code": TarjetaIncompletaError.error_code,
                "holes": error.hoyos,
            },
        )
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


_CON_CODIGO: tuple[type[Exception], ...] = (
    ScoringNotOpenYetError,
    TarjetaIncompletaError,
    *_ERRORES,
)
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
    body: SubmitTeeGroupScoreBodyDTO,
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


async def _y_la_vista(llamada, ver: VerAnotacionDePartidaUseCase, group_id: UUID, quien: UserId):
    try:
        await llamada
        return await ver.execute(group_id, quien)
    except PartidaNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_EXISTE) from e
    except _CON_CODIGO as e:
        return _respuesta(e)


@router.post(
    "/groups/{group_id}/scorecard",
    response_model=TeeGroupScoringViewDTO,
    summary="Entregar la tarjeta",
    description=(
        "Con los 18 hoyos validados (jugador y marcador coinciden); si no, 400 "
        "SCORECARD_NOT_READY con `holes`. La partida acaba cuando no queda ninguna en juego."
    ),
    tags=["Competitions - Tee groups"],
)
@limiter.limit("30/minute")
async def submit_tee_group_scorecard(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    group_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    entregar: EntregarTarjetaDePartidaUseCase = Depends(get_entregar_tarjeta_de_partida_use_case),
    ver: VerAnotacionDePartidaUseCase = Depends(get_ver_anotacion_de_partida_use_case),
):
    """200 con la partida."""
    quien = UserId(str(current_user.id))
    return await _y_la_vista(entregar.execute(group_id, quien), ver, group_id, quien)


@router.post(
    "/groups/{group_id}/scorecard/retire",
    response_model=TeeGroupScoringViewDTO,
    summary="Retirarse de la partida",
    description="En Medal queda NR; en Stableford cuenta lo jugado.",
    tags=["Competitions - Tee groups"],
)
@limiter.limit("30/minute")
async def retire_from_tee_group(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    group_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    retirarse: RetirarseDePartidaUseCase = Depends(get_retirarse_de_partida_use_case),
    ver: VerAnotacionDePartidaUseCase = Depends(get_ver_anotacion_de_partida_use_case),
):
    """200 con la partida."""
    quien = UserId(str(current_user.id))
    return await _y_la_vista(retirarse.execute(group_id, quien), ver, group_id, quien)


# ======================================================================================
# EL ORGANIZADOR (P3, P4, P6, P9, P11)
# ======================================================================================


@router.put(
    "/groups/{group_id}/players/{user_id}/holes/{hole}",
    response_model=TeeGroupScoringViewDTO,
    summary="Corregir un hoyo (organizador)",
    description=(
        "El lado del jugador (`own_score`), el del marcador (`marker_score`) o los dos: "
        "resuelve un desacuerdo o hace de marcador en una partida de uno. Queda registrado "
        "que lo metió el organizador. Una tarjeta cerrada se reabre antes."
    ),
    tags=["Competitions - Tee groups"],
)
@limiter.limit("60/minute")
async def correct_tee_group_hole(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    group_id: UUID,
    user_id: UUID,
    hole: int,
    body: CorrectHoleBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    corregir: CorregirHoyoDePartidaUseCase = Depends(get_corregir_hoyo_de_partida_use_case),
    ver: VerAnotacionDePartidaUseCase = Depends(get_ver_anotacion_de_partida_use_case),
):
    """200 con la partida."""
    quien = UserId(str(current_user.id))
    return await _y_la_vista(
        corregir.execute(group_id, user_id, hole, body, quien, current_user.is_admin),
        ver,
        group_id,
        quien,
    )


@router.post(
    "/groups/{group_id}/players/{user_id}/reopen",
    response_model=TeeGroupScoringViewDTO,
    summary="Reabrir una tarjeta (organizador)",
    tags=["Competitions - Tee groups"],
)
@limiter.limit("30/minute")
async def reopen_tee_group_card(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    group_id: UUID,
    user_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    reabrir: ReabrirTarjetaUseCase = Depends(get_reabrir_tarjeta_use_case),
    ver: VerAnotacionDePartidaUseCase = Depends(get_ver_anotacion_de_partida_use_case),
):
    """200 con la partida."""
    quien = UserId(str(current_user.id))
    return await _y_la_vista(
        reabrir.execute(group_id, user_id, quien, current_user.is_admin), ver, group_id, quien
    )


@router.post(
    "/groups/{group_id}/players/{user_id}/no-show",
    response_model=TeeGroupScoringViewDTO,
    summary="Marcar como no presentado (organizador)",
    tags=["Competitions - Tee groups"],
)
@limiter.limit("30/minute")
async def mark_tee_group_no_show(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    group_id: UUID,
    user_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    marcar: MarcarNoPresentadoUseCase = Depends(get_marcar_no_presentado_use_case),
    ver: VerAnotacionDePartidaUseCase = Depends(get_ver_anotacion_de_partida_use_case),
):
    """200 con la partida."""
    quien = UserId(str(current_user.id))
    return await _y_la_vista(
        marcar.execute(group_id, user_id, quien, current_user.is_admin), ver, group_id, quien
    )


@router.post(
    "/rounds/{round_id}/groups/close",
    response_model=TeeGroupsResponseDTO,
    summary="Cerrar las partidas de una franja (organizador)",
    description=(
        "La red: las tarjetas aún en juego quedan entregadas si están completas, no "
        "presentado si no tienen ningún hoyo validado, y retirado si van a medias."
    ),
    tags=["Competitions - Tee groups"],
)
@limiter.limit("30/minute")
async def close_tee_window_groups(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    round_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    cerrar: CerrarFranjaUseCase = Depends(get_cerrar_franja_use_case),
):
    """200 con las partidas de la franja."""
    try:
        return await cerrar.execute(round_id, UserId(str(current_user.id)), current_user.is_admin)
    except RoundNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_EXISTE) from e
    except _CON_CODIGO as e:
        return _respuesta(e)


# ======================================================================================
# CLASIFICACIONES
# ======================================================================================


def _sin_clasificacion() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Solo hay clasificación en un Stableford o un Medal.",
            "error_code": "NOT_STROKE_PLAY",
        },
    )


@router.get(
    "/rounds/{round_id}/standings",
    response_model=StandingsResponseDTO,
    summary="Clasificación de una franja",
    description=(
        "Neta, solo hoyos validados, con «tras N» y filtro de categoría. Sin desempate "
        "automático: los empatados comparten puesto."
    ),
    tags=["Competitions - Tee groups"],
)
async def get_tee_window_standings(
    round_id: UUID,
    category: int | None = None,
    current_user: UserResponseDTO = Depends(get_current_user),  # noqa: ARG001 - con sesión
    clasificacion: ClasificacionDeLaFranjaUseCase = Depends(
        get_clasificacion_de_la_franja_use_case
    ),
):
    """200 con la clasificación de la franja."""
    try:
        return await clasificacion.execute(round_id, category)
    except PartidasError:
        return _sin_clasificacion()


@router.get(
    "/{competition_id}/standings",
    response_model=StandingsResponseDTO,
    summary="Clasificación general",
    description="Neta, con la regla de la competición (acumulado o mejor tarjeta) y categorías.",
    tags=["Competitions - Tee groups"],
)
async def get_overall_standings(
    competition_id: UUID,
    category: int | None = None,
    current_user: UserResponseDTO = Depends(get_current_user),  # noqa: ARG001 - con sesión
    clasificacion: ClasificacionGeneralUseCase = Depends(get_clasificacion_general_use_case),
):
    """200 con la general."""
    try:
        return await clasificacion.execute(competition_id, category)
    except PartidasError:
        return _sin_clasificacion()


@router.get(
    "/{competition_id}/standings/scratch",
    response_model=StandingsResponseDTO,
    summary="Clasificación scratch",
    description=(
        "Sin categorías, con la misma regla: hasta el 25.º más los empatados, y `me` con "
        "la fila de quien mira si queda fuera."
    ),
    tags=["Competitions - Tee groups"],
)
async def get_scratch_standings(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    clasificacion: ClasificacionScratchUseCase = Depends(get_clasificacion_scratch_use_case),
):
    """200 con el scratch."""
    try:
        return await clasificacion.execute(competition_id, UserId(str(current_user.id)))
    except PartidasError:
        return _sin_clasificacion()
