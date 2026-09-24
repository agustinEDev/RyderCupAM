"""Rutas de los sobres (FE #655)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from src.config.dependencies import (
    get_current_user,
    get_envelopes_use_case,
    get_list_my_pending_envelopes_use_case,
    get_list_my_sessions_without_matches_use_case,
    get_reset_envelopes_use_case,
    get_reveal_envelopes_use_case,
    get_submit_envelope_use_case,
)
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.envelope_dto import (
    EnvelopeDTO,
    EnvelopesViewDTO,
    PendingEnvelopeDTO,
    ResetEnvelopesResponseDTO,
    RevealEnvelopesResponseDTO,
)
from src.modules.competition.application.dto.match_generation_block_dto import (
    SessionWithoutMatchesDTO,
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
from src.modules.competition.application.use_cases.list_my_pending_envelopes_use_case import (
    ListMyPendingEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.list_my_sessions_without_matches_use_case import (
    ListMySessionsWithoutMatchesUseCase,
)
from src.modules.competition.application.use_cases.reset_envelopes_use_case import (
    NothingToResetError,
    ResetEnvelopesUseCase,
    SessionAlreadyPlayedError,
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
    reveal_when_both_ready: bool = Field(
        False,
        description=(
            "Pide abrir los sobres en cuanto estén los dos, sin esperar a la "
            "hora. Hacen falta LOS DOS capitanes para que valga: con uno solo "
            "se espera, porque el otro tiene derecho a su plazo."
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
        return await use_case.execute(
            round_id,
            UserId(str(current_user.id)),
            body.entries,
            sin_esperar=body.reveal_when_both_ready,
        )
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
        return await use_case.execute(
            round_id, UserId(str(current_user.id)), is_admin=current_user.is_admin
        )
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
        "listas por posición. A partir de aquí los partidos de esa sesión salen "
        "de los sobres. Lo pide el organizador o cualquiera de los dos capitanes, "
        "y **hacen falta los dos sobres entregados**: abrir es lo que desvela el "
        "orden de juego. Lo que falte se rellena por hándicap cuando los abre el "
        "reloj al vencer el plazo, o cuando los abre el organizador en una sesión "
        "sin plazo que vencer (un campo sin zona horaria)."
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


@router.post(
    "/rounds/{round_id}/envelopes/reset",
    response_model=ResetEnvelopesResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Rehacer los sobres de una sesión",
    description=(
        "Tira los dos sobres **y los partidos** de esa sesión para que los "
        "capitanes vuelvan a entregar. Cuando uno no llega a tiempo, lo que "
        "viene después no es editar el resultado: es rehacer el proceso. Lo "
        "pide **solo el organizador** —es quien arbitra— y solo mientras no se "
        "haya jugado nada de esa sesión."
    ),
    tags=["Competitions - Envelopes"],
)
@limiter.limit("10/minute")
async def reset_envelopes(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    round_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ResetEnvelopesUseCase = Depends(get_reset_envelopes_use_case),
):
    """Rehace los sobres de una sesión (FE #655)."""
    try:
        return await use_case.execute(
            round_id, UserId(str(current_user.id)), is_admin=current_user.is_admin
        )
    except (RoundNotFoundError, CompetitionNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotCompetitionCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except (SessionAlreadyPlayedError, NothingToResetError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/me/pending-envelopes",
    response_model=list[PendingEnvelopeDTO],
    status_code=status.HTTP_200_OK,
    summary="Mis sobres sin entregar",
    description=(
        "Las sesiones en las que quien pregunta capitanea y todavía no ha "
        "entregado su sobre, de la más próxima a la más lejana. Alimenta el "
        "bloque «Requiere tu Atención» del panel: sin esto, un capitán solo se "
        "entera entrando sesión por sesión en la agenda de cada competición, y "
        "el plazo le vence sin saberlo. Vacío para quien no capitanea nada."
    ),
    tags=["Competitions - Envelopes"],
)
# Lo dispara el panel de TODO el mundo en cada montaje, y en produccion el
# cubo es unico para toda la aplicacion (ADR-038): con 60/min, doce moviles
# volviendo a «Inicio» en un torneo se llevan un 429. Como la llamada va
# dentro de un `allSettled`, el fallo seria mudo: al capitan simplemente no le
# saldria el aviso. El GET de la sala de draft subio a 300 por lo mismo
@limiter.limit("300/minute")
async def list_my_pending_envelopes(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ListMyPendingEnvelopesUseCase = Depends(get_list_my_pending_envelopes_use_case),
):
    """Los sobres que me faltan por entregar (FE #655)."""
    return await use_case.execute(UserId(str(current_user.id)))


@router.get(
    "/me/sessions-without-matches",
    response_model=list[SessionWithoutMatchesDTO],
    status_code=status.HTTP_200_OK,
    summary="Mis sesiones que se quedaron sin partidos",
    description=(
        "Las sesiones de las competiciones que organiza quien pregunta cuyos "
        "sobres ya se abrieron y cuyos partidos NO se pudieron crear, con el "
        "motivo y a quién le falta qué (BE #361). Alimenta el bloque «Requiere "
        "tu Atención» del panel: sin esto, el organizador se enteraría a la "
        "hora de jugar. Vacío casi siempre."
    ),
    tags=["Competitions - Envelopes"],
)
# El mismo panel que dispara la de los sobres pendientes, y por lo mismo
@limiter.limit("300/minute")
async def list_my_sessions_without_matches(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ListMySessionsWithoutMatchesUseCase = Depends(
        get_list_my_sessions_without_matches_use_case
    ),
):
    """Las sesiones que tengo que arreglar para que tengan partidos (BE #361)."""
    return await use_case.execute(UserId(str(current_user.id)))
