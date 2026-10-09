"""
Rutas: las partidas de las franjas de stroke play (#251, PR 4).

Bajo `/api/v1/competitions`. Los errores con lista de jugadores llevan
`error_code` en la raíz, como la Ryder: la pantalla los pone en su idioma.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.config.dependencies import get_current_user, get_generar_partidas_use_case
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.partidas_dto import (
    GenerateTeeGroupsRequestDTO,
    TeeGroupsResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
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
    GenerarPartidasUseCase,
)
from src.modules.competition.domain.entities.partida import PartidaEmpezadaError
from src.modules.competition.domain.services.plazo_de_partidas import PlazoCerradoError
from src.modules.competition.domain.services.reparto_de_partidas import RepartoImposibleError
from src.modules.competition.infrastructure.api.v1.competition_state_routes import (
    respuesta_con_jugadores,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.value_objects.user_id import UserId

router = APIRouter()


# Error -> (estado HTTP, error_code). Claves y no frases: la pantalla los traduce
_CON_CODIGO: dict[type[Exception], tuple[int, str]] = {
    PlazoCerradoError: (status.HTTP_400_BAD_REQUEST, "GROUPS_WINDOW_CLOSED"),
    PartidaEmpezadaError: (status.HTTP_409_CONFLICT, "GROUP_ALREADY_STARTED"),
    ZonaDesconocidaError: (status.HTTP_400_BAD_REQUEST, "COURSE_WITHOUT_TIMEZONE"),
    RepartoImposibleError: (status.HTTP_400_BAD_REQUEST, "NOT_ENOUGH_PLAYERS"),
}
# Error con la lista de jugadores afectados -> error_code (400)
_CON_JUGADORES: dict[type[Exception], str] = {
    JugadoresSinHandicapError: "PLAYERS_WITHOUT_HANDICAP",
    JugadoresSinBarraError: "PLAYERS_WITHOUT_TEE",
}
_ERRORES_CON_CODIGO = (*_CON_CODIGO, *_CON_JUGADORES)


def _respuesta(error: Exception) -> JSONResponse:
    """La respuesta con `error_code` de un error de las partidas."""
    for tipo, codigo in _CON_JUGADORES.items():
        if isinstance(error, tipo):
            return respuesta_con_jugadores(error, codigo, error.players)
    for tipo, (status_code, codigo) in _CON_CODIGO.items():
        if isinstance(error, tipo):
            return JSONResponse(
                status_code=status_code, content={"detail": str(error), "error_code": codigo}
            )
    raise error


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
    try:
        return await use_case.execute(
            round_id, body, UserId(str(current_user.id)), current_user.is_admin
        )
    except (RoundNotFoundError, CompetitionNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotCompetitionCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except PartidasError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except _ERRORES_CON_CODIGO as e:
        return _respuesta(e)
