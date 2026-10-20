"""
RefrescoRfeg - Refresca con la RFEG el hándicap de un jugador antes de usarlo (HM-1a).

Vivía dentro de la generación de partidos. Sale aquí porque el stroke play lo
necesita también al fijar la categoría de cada jugador (RyderCupAM#251).

Las reglas son las de siempre: solo jugadores de España, como mucho una vez al
día (el mismo límite que el refresco del propio jugador al entrar), y nunca
bloquea lo que se está haciendo: un fallo de red o de guardado se registra y se
sigue con el hándicap que había.

Solo se llama para quien NO tiene hándicap propio en la inscripción: ese lo
puso el organizador y la RFEG no lo cambia. Esa decisión es de quien llama.
"""

import logging
from datetime import UTC, datetime

from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    ResultadoRefresco,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService

logger = logging.getLogger(__name__)


class RefrescoRfeg:
    """Pregunta a la RFEG por el hándicap de un jugador si le toca."""

    def __init__(
        self,
        handicap_service: HandicapService | None,
        user_repository: UserRepositoryInterface,
    ):
        """
        Args:
            handicap_service: El servicio de la RFEG; sin él no se refresca nada
            user_repository: Donde se guarda el hándicap nuevo
        """
        self._handicap_service = handicap_service
        self._user_repo = user_repository

    async def si_toca(self, user: User) -> None:
        """Refresca y guarda el hándicap del jugador, si es de España y no se hizo hoy."""
        if user.handicap_updated_at is not None and (
            user.handicap_updated_at.date() == datetime.now(UTC).date()
        ):
            return
        await self.consultar(user)

    async def consultar(self, user: User) -> ResultadoRefresco:
        """
        Pregunta a la RFEG siempre, sin el límite de una vez al día, y dice qué pasó.

        Es la de una actualización de hándicaps de una competición (#251): al
        cerrar las inscripciones cuenta lo que diga la RFEG en ese momento,
        aunque el jugador ya se refrescara hoy al entrar.
        """
        if self._handicap_service is None:
            return ResultadoRefresco.FALLIDO

        country_code_value = user.country_code.value if user.country_code else None
        if country_code_value != "ES":
            return ResultadoRefresco.SIN_LICENCIA_ESPANOLA

        try:
            handicap_value = await self._handicap_service.search_handicap(user.get_full_name())
        except Exception:
            logger.warning(
                "RFEG lookup failed for %s before using it in a competition",
                user.get_full_name(),
                exc_info=True,
            )
            return ResultadoRefresco.FALLIDO

        if handicap_value is None:
            return ResultadoRefresco.NO_ENCONTRADO

        try:
            user.update_handicap(handicap_value)
            await self._user_repo.save(user)
        except Exception:
            logger.error(
                "Failed to persist RFEG handicap for %s before using it in a competition",
                user.get_full_name(),
                exc_info=True,
            )
            return ResultadoRefresco.FALLIDO
        return ResultadoRefresco.ACTUALIZADO
