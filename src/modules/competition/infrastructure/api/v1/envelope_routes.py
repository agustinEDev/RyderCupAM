"""Rutas de los sobres (FE #655)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from src.config.dependencies import (
    get_current_user,
    get_envelopes_use_case,
    get_reveal_envelopes_use_case,
    get_submit_envelope_use_case,
)
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.envelope_dto import (
    EnvelopeDTO,
    EnvelopesViewDTO,
    RevealEnvelopesResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
    NotCompetitionParticipantError,
    RoundNotFoundError,
)
from src.modules.competition.application.services.envelope_desk import (
    RoundAlreadyScheduledError,
)
from src.modules.competition.application.use_cases.get_envelopes_use_case import (
    GetEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.reveal_envelopes_use_case import (
    RevealEnvelopesUseCase,
    RivalEnvelopeMissingError,
)
from src.modules.competition.application.use_cases.submit_envelope_use_case import (
    NotATeamCaptainError,
    SubmitEnvelopeUseCase,
)
from src.modules.competition.domain.entities.competition import TeamsNotAssignedError
from src.modules.competition.domain.entities.envelope import (
    DuplicatedPlayerError,
    EmptyEnvelopeError,
    EnvelopeAlreadyRevealedError,
    OddTeamForPairsError,
    PlayerNotInTeamError,
    RowSizeError,
    TeamNotFullyEnteredError,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.value_objects.user_id import UserId

router = APIRouter()


class SubmitEnvelopeBodyDTO(BaseModel):
    """La lista ordenada del capitán."""

    entries: list[list[UUID]] = Field(
        ...,
        description=(
            "Las filas, en orden: un jugador por fila en individuales, dos en "
            "los formatos de parejas. El equipo NO se manda: sale de quién "
            "firma la petición."
        ),
    )


# Lo que es culpa de quien pide: una lista que no cuadra con su equipo, un
# sobre ya abierto o unos equipos todavia sin repartir. `ValueError` pelado NO:
# se llevaria por delante los de Pydantic y los de un dato mal guardado, y un
# 500 de verdad saldria como un 400 «culpa tuya»
_ERRORES_DEL_SOBRE = (
    EnvelopeAlreadyRevealedError,
    PlayerNotInTeamError,
    TeamNotFullyEnteredError,
    TeamsNotAssignedError,
    EmptyEnvelopeError,
    RowSizeError,
    DuplicatedPlayerError,
    RoundAlreadyScheduledError,
    OddTeamForPairsError,
)


@router.put(
    "/rounds/{round_id}/envelope",
    response_model=EnvelopeDTO,
    status_code=status.HTTP_200_OK,
    summary="Entregar el sobre de tu equipo",
    description=(
        "El capitán entrega —o corrige— su lista ordenada para esa sesión: un "
        "jugador por fila en individuales, dos en los formatos de parejas. Aquí "
        "juegan todos, así que tienen que estar todos los de su equipo. El "
        "equipo no se manda en el cuerpo: sale de quién firma la petición, que "
        "si no se podría entregar el sobre del rival. Se puede corregir hasta "
        "que los sobres se abren."
    ),
    tags=["Competitions - Envelopes"],
)
@limiter.limit("30/minute")
async def submit_envelope(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    round_id: UUID,
    body: SubmitEnvelopeBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: SubmitEnvelopeUseCase = Depends(get_submit_envelope_use_case),
):
    """Entrega el sobre del capitán (FE #655)."""
    try:
        return await use_case.execute(round_id, UserId(str(current_user.id)), body.entries)
    except (RoundNotFoundError, CompetitionNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotATeamCaptainError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except _ERRORES_DEL_SOBRE as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/rounds/{round_id}/envelopes",
    response_model=EnvelopesViewDTO,
    status_code=status.HTTP_200_OK,
    summary="Ver los sobres de una sesión",
    description=(
        "Devuelve lo que puede ver quien pregunta. Un capitán ve el suyo y si el "
        "rival ya entregó, **nunca su contenido**: verlo antes de tiempo es el "
        "juego entero. Abiertos, los ve todo el mundo con los enfrentamientos ya "
        "cruzados por posición."
    ),
    tags=["Competitions - Envelopes"],
)
@limiter.limit("120/minute")
async def get_envelopes(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    round_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetEnvelopesUseCase = Depends(get_envelopes_use_case),
):
    """Devuelve los sobres de una sesión (FE #655)."""
    try:
        return await use_case.execute(round_id, UserId(str(current_user.id)))
    except (RoundNotFoundError, CompetitionNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotCompetitionParticipantError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except _ERRORES_DEL_SOBRE as e:
        # Mirar los sobres de una competicion sin equipos repartidos es una
        # peticion valida con una respuesta clara, no un 500
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/rounds/{round_id}/envelopes/reveal",
    response_model=RevealEnvelopesResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Abrir los sobres de una sesión",
    description=(
        "Abre los dos a la vez y devuelve los enfrentamientos, cruzando las dos "
        "listas por posición. El sobre que no llegó lo rellena la aplicación por "
        "hándicap, sin tocar el del capitán que sí entregó. A partir de aquí los "
        "partidos de esa sesión salen de los sobres. Lo hace el organizador o "
        "cualquiera de los dos capitanes."
    ),
    tags=["Competitions - Envelopes"],
)
@limiter.limit("10/minute")
async def reveal_envelopes(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    round_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: RevealEnvelopesUseCase = Depends(get_reveal_envelopes_use_case),
):
    """Abre los sobres de una sesión (FE #655)."""
    try:
        return await use_case.execute(
            round_id, UserId(str(current_user.id)), is_admin=current_user.is_admin
        )
    except (RoundNotFoundError, CompetitionNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotCompetitionCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except RivalEnvelopeMissingError as e:
        # 409 y no 400: la petición es correcta, es que todavía no toca
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except _ERRORES_DEL_SOBRE as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
