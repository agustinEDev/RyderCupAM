"""
ScoringOpeningService - Domain Service: cuando se abre la anotacion de un partido.

Un partido se podia anotar solo despues de que su creador pulsara START, con
cobertura. En un campo sin señal eso es fragil: si nadie lo pulsa, todos los
golpes vuelven rechazados y la vuelta se pierde (BE #305).

La anotacion se abre sola a una hora fija segun la sesion de la ronda, en la
zona horaria del CAMPO donde se juega esa ronda. START se queda para abrir antes.

Lo que decide es el reloj del SERVIDOR cuando llega el golpe, nunca una hora
enviada por el cliente: sin cobertura el movil no puede saber si el partido esta
abierto, y su reloj se puede tocar. Un golpe anotado en modo avion antes de la
hora entra sin problema si llega despues, que es el caso normal.
"""

import logging
from datetime import date, datetime, time

from src.modules.competition.domain.services.zona_horaria import zona_del_campo
from src.modules.competition.domain.value_objects.session_type import SessionType

logger = logging.getLogger(__name__)

# Decidido con el dueño del producto el 17 sep 2026. La hora es la LOCAL del
# campo: las seis de Canarias no son las seis de Madrid.
OPENING_HOUR_BY_SESSION: dict[SessionType, int] = {
    SessionType.MORNING: 6,
    SessionType.AFTERNOON: 12,
    SessionType.EVENING: 18,
}


class ScoringOpeningService:
    """Calcula a que hora abre la anotacion de un partido, y si ya abrio."""

    @staticmethod
    def opens_at(
        round_date: date | None,
        session_type: SessionType | None,
        timezone: str | None,
    ) -> datetime | None:
        """
        La hora a la que se puede empezar a anotar, con su desfase.

        Devuelve `None` cuando la ronda no tiene fecha o sesion —datos de antes
        de que existieran— porque entonces no hay hora que calcular: esos
        partidos siguen necesitando START.

        """
        # Sin fecha, sin sesion o sin zona no hay hora que calcular: esos
        # partidos siguen necesitando START
        if round_date is None or session_type is None or timezone is None:
            return None

        try:
            hour = OPENING_HOUR_BY_SESSION[SessionType(session_type)]
        except (ValueError, KeyError):
            # Una sesion que no conocemos no puede tumbar la LECTURA: esto se
            # llama tambien al pintar la vista de anotacion y el calendario
            logger.warning("Tipo de sesion desconocido al calcular la apertura: %s", session_type)
            return None

        # Una zona que no existe no puede tumbar la LECTURA: sin hora, no se
        # abre solo, que es justo lo que se quiere cuando no se sabe cuándo
        zone = zona_del_campo(timezone)
        if zone is None:
            return None

        return datetime.combine(round_date, time(hour=hour), tzinfo=zone)
