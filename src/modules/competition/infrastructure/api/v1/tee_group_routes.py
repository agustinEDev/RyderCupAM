"""
Rutas: las partidas de las franjas de stroke play (#251, PR 4).

Bajo `/api/v1/competitions`. Los errores llevan `error_code` en la raíz, como la
Ryder: claves y no frases, la pantalla los pone en su idioma (24 sep).
"""

from collections.abc import Awaitable
from typing import TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from src.config.dependencies import (
    get_borrar_partidas_use_case,
    get_cambiar_marcadores_use_case,
    get_current_user,
    get_generar_partidas_use_case,
    get_mis_partidas_use_case,
    get_mover_jugador_de_partida_use_case,
    get_reordenar_partidas_use_case,
    get_ver_partidas_use_case,
)
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.partidas_dto import (
    GenerateTeeGroupsRequestDTO,
    MoveTeeGroupPlayerRequestDTO,
    MyTeeGroupsResponseDTO,
    ReorderTeeGroupsRequestDTO,
    TeeGroupMarkersRequestDTO,
    TeeGroupsResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
    PartidaNotFoundError,
    PartidasError,
    RoundNotFoundError,
)
from src.modules.competition.application.services.jornadas_de_la_competicion import (
    ZonaDesconocidaError,
)
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresSinBarraError,
    JugadoresSinHandicapError,
)
from src.modules.competition.application.use_cases.partidas_use_case import (
    BorrarPartidasUseCase,
    CambiarMarcadoresUseCase,
    GenerarPartidasUseCase,
    MisPartidasUseCase,
    MoverJugadorUseCase,
    ReordenarPartidasUseCase,
    VerPartidasUseCase,
)
from src.modules.competition.domain.entities.partida import PartidaEmpezadaError
from src.modules.competition.domain.services.marcadores_en_cadena import (
    MarcadoresInvalidosError,
)
from src.modules.competition.domain.services.movimientos_de_partidas import (
    MovimientoImposibleError,
)
from src.modules.competition.domain.services.plazo_de_partidas import PlazoCerradoError
from src.modules.competition.domain.services.reparto_de_partidas import RepartoImposibleError
from src.modules.competition.infrastructure.api.v1.competition_state_routes import (
    respuesta_con_jugadores,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.value_objects.user_id import UserId

router = APIRouter()

T = TypeVar("T")

# Error -> (estado HTTP, error_code)
_CON_CODIGO: dict[type[Exception], tuple[int, str]] = {
    PlazoCerradoError: (status.HTTP_400_BAD_REQUEST, "GROUPS_WINDOW_CLOSED"),
    PartidaEmpezadaError: (status.HTTP_409_CONFLICT, "GROUP_ALREADY_STARTED"),
    ZonaDesconocidaError: (status.HTTP_400_BAD_REQUEST, "COURSE_WITHOUT_TIMEZONE"),
    RepartoImposibleError: (status.HTTP_400_BAD_REQUEST, "NOT_ENOUGH_PLAYERS"),
    MarcadoresInvalidosError: (status.HTTP_400_BAD_REQUEST, "INVALID_MARKERS"),
}
# Error con la lista de jugadores afectados -> error_code (400)
_CON_JUGADORES: dict[type[Exception], str] = {
    JugadoresSinHandicapError: "PLAYERS_WITHOUT_HANDICAP",
    JugadoresSinBarraError: "PLAYERS_WITHOUT_TEE",
}
_ERRORES_CON_CODIGO: tuple[type[Exception], ...] = (
    *_CON_CODIGO,
    *_CON_JUGADORES,
    MovimientoImposibleError,
)


def _respuesta(error: Exception) -> JSONResponse:
    """La respuesta con `error_code` de un error de las partidas."""
    if isinstance(error, MovimientoImposibleError):
        # Cada movimiento imposible trae su clave
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(error), "error_code": error.codigo},
        )
    for tipo, codigo in _CON_JUGADORES.items():
        if isinstance(error, tipo):
            return respuesta_con_jugadores(error, codigo, error.players)
    for tipo, (status_code, codigo) in _CON_CODIGO.items():
        if isinstance(error, tipo):
            return JSONResponse(
                status_code=status_code, content={"detail": str(error), "error_code": codigo}
            )
    raise error


async def _responder(llamada: Awaitable[T]) -> T | JSONResponse:
    """Ejecuta el caso de uso y traduce sus errores, los mismos en todas las rutas."""
    try:
        return await llamada
    except (RoundNotFoundError, CompetitionNotFoundError, PartidaNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotCompetitionCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except PartidasError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except _ERRORES_CON_CODIGO as e:
        return _respuesta(e)


def _quien(current_user: UserResponseDTO) -> UserId:
    return UserId(str(current_user.id))


@router.post(
    "/rounds/{round_id}/groups/generate",
    response_model=TeeGroupsResponseDTO,
    summary="Generar las partidas de una franja",
    description=(
        "Stableford o Medal. El organizador reparte por hándicap fijado a los jugadores con "
        "plaza en la franja, del cierre de inscripciones a la primera salida, y reemplaza las "
        "partidas que hubiera. `order`: HIGH_FIRST o LOW_FIRST."
    ),
    tags=["Competitions - Tee groups"],
)
@limiter.limit("30/minute")
async def generate_tee_groups(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    round_id: UUID,
    body: GenerateTeeGroupsRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GenerarPartidasUseCase = Depends(get_generar_partidas_use_case),
):
    """200 con las partidas de la franja; 400/409 con `error_code` si no se puede."""
    return await _responder(
        use_case.execute(round_id, body, _quien(current_user), current_user.is_admin)
    )


@router.post(
    "/rounds/{round_id}/groups/players",
    response_model=TeeGroupsResponseDTO,
    summary="Mover a un jugador de partida",
    description=(
        "A una partida con hueco, intercambiando con uno de una llena (`swap_with_user_id`) "
        "o, sin `group_id`, a una nueva al final si quedan salidas (nace incompleta). El "
        "origen nunca se queda con uno solo salvo intercambio; una partida que se vacía "
        "desaparece y las de detrás suben."
    ),
    tags=["Competitions - Tee groups"],
)
@limiter.limit("30/minute")
async def move_tee_group_player(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    round_id: UUID,
    body: MoveTeeGroupPlayerRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: MoverJugadorUseCase = Depends(get_mover_jugador_de_partida_use_case),
):
    """200 con las partidas; 400 con la clave del motivo si no se puede."""
    return await _responder(
        use_case.execute(
            round_id,
            body.user_id,
            body.group_id,
            body.swap_with_user_id,
            _quien(current_user),
            current_user.is_admin,
        )
    )


@router.put(
    "/rounds/{round_id}/groups/order",
    response_model=TeeGroupsResponseDTO,
    summary="Reordenar las partidas de una franja",
    description="Todas las partidas, una vez, en el nuevo orden de salida.",
    tags=["Competitions - Tee groups"],
)
@limiter.limit("30/minute")
async def reorder_tee_groups(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    round_id: UUID,
    body: ReorderTeeGroupsRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ReordenarPartidasUseCase = Depends(get_reordenar_partidas_use_case),
):
    """200 con las partidas; 400 INVALID_GROUP_ORDER si no van todas una vez."""
    return await _responder(
        use_case.execute(round_id, body.group_ids, _quien(current_user), current_user.is_admin)
    )


@router.put(
    "/groups/{group_id}/markers",
    response_model=TeeGroupsResponseDTO,
    summary="Cambiar los marcadores de una partida",
    description="Todos los jugadores de la partida; cada uno marca a uno y nadie a sí mismo.",
    tags=["Competitions - Tee groups"],
)
@limiter.limit("30/minute")
async def change_tee_group_markers(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    group_id: UUID,
    body: TeeGroupMarkersRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CambiarMarcadoresUseCase = Depends(get_cambiar_marcadores_use_case),
):
    """200 con las partidas de su franja; 400 INVALID_MARKERS si no valen."""
    return await _responder(
        use_case.execute(
            group_id,
            {m.user_id: m.marks_user_id for m in body.markers},
            _quien(current_user),
            current_user.is_admin,
        )
    )


@router.delete(
    "/rounds/{round_id}/groups",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar las partidas de una franja",
    description="Para empezar de cero, con el mismo plazo que generar.",
    tags=["Competitions - Tee groups"],
)
@limiter.limit("30/minute")
async def delete_tee_groups(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    round_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: BorrarPartidasUseCase = Depends(get_borrar_partidas_use_case),
):
    """204; 400/409 con `error_code` fuera de plazo."""
    resultado = await _responder(
        use_case.execute(round_id, _quien(current_user), current_user.is_admin)
    )
    if isinstance(resultado, JSONResponse):
        return resultado
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/rounds/{round_id}/groups",
    response_model=TeeGroupsResponseDTO,
    summary="Ver las partidas de una franja",
    description=(
        "Cualquiera con sesión. `editable` dice si el organizador aún puede generarlas o "
        "cambiarlas; `unassigned_player_ids`, quién tiene plaza y no partida."
    ),
    tags=["Competitions - Tee groups"],
)
async def get_tee_groups(
    round_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),  # noqa: ARG001 - con sesión
    use_case: VerPartidasUseCase = Depends(get_ver_partidas_use_case),
):
    """200 con las partidas de la franja."""
    return await _responder(use_case.execute(round_id))


@router.get(
    "/{competition_id}/groups/me",
    response_model=MyTeeGroupsResponseDTO,
    summary="Mis partidas en una competición",
    description="Las partidas de quien pregunta, por día y hora de salida, con sus compañeros.",
    tags=["Competitions - Tee groups"],
)
async def get_my_tee_groups(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: MisPartidasUseCase = Depends(get_mis_partidas_use_case),
):
    """200 con mis partidas (vacío si no juego ninguna)."""
    return await use_case.execute(competition_id, _quien(current_user))
