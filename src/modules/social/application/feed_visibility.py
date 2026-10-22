"""
Lo que una pagina de actividad ya no debe enseñar aunque siga guardado.

Vive aparte porque lo comparten el feed y la actividad de un perfil: las dos
pintan las mismas tarjetas, y la que se quedara atras enseñaria lo que no debe.
"""

from collections.abc import Sequence

from src.modules.social.application.ports.tournament_visibility_interface import (
    TournamentVisibilityInterface,
)
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType

_APUNTADO = ActivityEventType.ENROLLED_IN_TOURNAMENT


async def sin_apuntados_a_privados(
    eventos: Sequence[ActivityEvent], tournaments: TournamentVisibilityInterface | None
) -> list[ActivityEvent]:
    """
    La pagina sin los «X se ha apuntado» de torneos que ahora son privados
    (tabla del 22 oct 2026, E).

    Al pasar a privado se borran, pero ese borrado puede fallar sin tumbar la
    accion; esto es la red. Se pregunta por todos los torneos de la pagina de
    una vez. Quien llama calcula el cursor ANTES de filtrar: la pagina puede
    quedar corta, pero el cursor sigue tras la ultima fila leida, asi que no se
    pierde ni se repite nada. Si el torneo vuelve a ser publico, lo que ya se
    borro no reaparece.
    """
    if tournaments is None:
        return list(eventos)
    ids = {
        competition_id
        for evento in eventos
        if evento.type == _APUNTADO
        and isinstance(competition_id := evento.payload.get("competition_id"), str)
    }
    if not ids:
        return list(eventos)
    privados = await tournaments.private_ids(sorted(ids))
    return [
        evento
        for evento in eventos
        if not (evento.type == _APUNTADO and evento.payload.get("competition_id") in privados)
    ]
