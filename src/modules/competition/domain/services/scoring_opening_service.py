"""
ScoringOpeningService - Domain Service: cuando se abre la anotacion de un partido.

Un partido se podia anotar solo despues de que su creador pulsara START, con
cobertura. En un campo sin señal eso es fragil: si nadie lo pulsa, todos los
golpes vuelven rechazados y la vuelta se pierde (BE #305).

La anotacion se abre sola a una hora fija segun la sesion de la ronda, en la
zona horaria de la competicion. START se queda para abrir antes.

Lo que decide es el reloj del SERVIDOR cuando llega el golpe, nunca una hora
enviada por el cliente: sin cobertura el movil no puede saber si el partido esta
abierto, y su reloj se puede tocar. Un golpe anotado en modo avion antes de la
hora entra sin problema si llega despues, que es el caso normal.
"""

import logging
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.modules.competition.domain.value_objects.session_type import SessionType

logger = logging.getLogger(__name__)

# Decidido con el dueño del producto el 17 sep 2026. La hora es la LOCAL de la
# competicion: las seis de Canarias no son las seis de Madrid.
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
        timezone: str,
    ) -> datetime | None:
        """
        La hora a la que se puede empezar a anotar, con su desfase.

        Devuelve `None` cuando la ronda no tiene fecha o sesion —datos de antes
        de que existieran— porque entonces no hay hora que calcular: esos
        partidos siguen necesitando START.

        """
        if round_date is None or session_type is None:
            return None

        hour = OPENING_HOUR_BY_SESSION.get(SessionType(session_type))
        if hour is None:
            return None

        try:
            zone = ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            # Una zona que no existe no puede tumbar la LECTURA: esto se llama
            # tambien al pintar la vista de anotacion y el calendario, y la
            # entidad valida la zona al crearse, asi que llegar aqui significa
            # que el dato entro por otro sitio. Sin hora, el partido no se abre
            # solo —START sigue— pero todo lo demas se sigue viendo
            logger.warning("Zona horaria desconocida en una competicion: %s", timezone)
            return None

        return datetime.combine(round_date, time(hour=hour), tzinfo=zone)

    @staticmethod
    def is_open(
        round_date: date | None,
        session_type: SessionType | None,
        timezone: str,
        now: datetime | None = None,
    ) -> bool:
        """
        Si a `now` —por omision, el reloj del servidor— ya se puede anotar.

        Sin tope por arriba, a proposito (decidido el 18 sep 2026): un golpe que
        llega dias tarde abre el partido igual, porque un golpe atascado en un
        movil sin cobertura es justo para lo que esto existe.
        """
        opens_at = ScoringOpeningService.opens_at(round_date, session_type, timezone)
        if opens_at is None:
            return False

        return (now or datetime.now(UTC)) >= opens_at
