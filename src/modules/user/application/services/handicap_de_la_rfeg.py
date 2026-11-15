"""
Avisar de que la RFEG dio el hándicap de un jugador (D1 y D4, 16 nov 2026).

Lo usan los caminos del perfil que preguntan a la RFEG: el botón del perfil,
el refresco al entrar y la actualización de varios a la vez. Solo cuando lo
dio la RFEG (nunca un hándicap puesto a mano), y después de guardarlo.
"""

import logging

from src.modules.user.application.ports.handicap_de_la_rfeg_port import (
    IHandicapEncontradoEnLaRfeg,
)
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


async def avisar_de_la_rfeg(
    al_encontrarlo: IHandicapEncontradoEnLaRfeg | None, user_id: UserId, handicap: float
) -> None:
    """Avisa de que la RFEG lo dio; si falla, el hándicap ya guardado se queda."""
    if al_encontrarlo is None:
        return
    try:
        await al_encontrarlo.encontrado(user_id, handicap)
    except Exception:
        logger.exception("Could not pass the RFEG handicap of %s to its competitions", user_id)
