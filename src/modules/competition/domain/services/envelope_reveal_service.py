"""
EnvelopeRevealService - Cuando se abren solos los sobres de una sesion (FE #655).

Decidido con el dueno del producto el 23 sep: **6 horas antes de la sesion**.
Esa hora es ademas el PLAZO: los sobres tienen que estar cubiertos antes, y lo
que no haya llegado lo rellena la aplicacion al abrirlos.
La hora de una sesion ya estaba definida en el producto —06:00 la de manana,
12:00 la de tarde, 18:00 la de noche, en hora local del campo—, asi que esto no
inventa un reloj nuevo: se apoya en el mismo que abre la anotacion (BE #305).

Pero el reloj no manda solo: **nunca antes de que acabe la sesion anterior**. Un
un plazo a secas abriria los sobres de la tarde a las 06:00 del mismo dia, con
la sesion de manana empezando, y se perderia lo que da sentido a esperar:
elegir con el marcador delante.

Y para que eso no se atasque, la anterior se da por acabada cuando sus partidos
terminan **o** cuando llega la hora de esta, lo que ocurra primero: un partido
que nadie cierra no puede dejar la sesion siguiente sin enfrentamientos.
"""

from datetime import date, datetime, timedelta

from src.modules.competition.domain.services.scoring_opening_service import (
    ScoringOpeningService,
)
from src.modules.competition.domain.value_objects.session_type import SessionType

# Decidido el 23 sep 2026. Es tambien el plazo para entregar: a esta hora se
# abren, y lo que no este dentro lo rellena la aplicacion
HOURS_BEFORE_SESSION = 6


class EnvelopeRevealService:
    """Calcula cuando se abren los sobres de una sesion, y si ya toca."""

    @staticmethod
    def scheduled_for(
        round_date: date | None,
        session_type: SessionType | None,
        timezone: str | None,
    ) -> datetime | None:
        """
        La hora a la que los sobres se abren solos.

        Returns:
            La hora con su desfase, o None si falta el dato para calcularla
            —fecha, sesion o zona—. Sin hora no se abren solos nunca, y
            entonces los abre a mano el que arbitra: es la unica salida que le
            queda a esa sesion
        """
        comienzo = ScoringOpeningService.opens_at(round_date, session_type, timezone)
        if comienzo is None:
            return None
        return comienzo - timedelta(hours=HOURS_BEFORE_SESSION)

    @staticmethod
    def is_due(scheduled: datetime | None, la_anterior_acabo: bool, ahora: datetime) -> bool:
        """
        Indica si ya toca abrirlos.

        Args:
            scheduled: La hora programada, o None si no se pudo calcular
            la_anterior_acabo: Si la sesion anterior ya termino
            ahora: La hora del SERVIDOR

        Returns:
            True solo si ha llegado la hora Y la sesion anterior acabo
        """
        if scheduled is None:
            return False
        return ahora >= scheduled and la_anterior_acabo

    @staticmethod
    def previous_session_is_over(
        partidos_pendientes: int | None,
        comienzo_de_esta: datetime | None,
        ahora: datetime,
    ) -> bool:
        """
        Indica si la sesion anterior se puede dar por acabada.

        Args:
            partidos_pendientes: Los suyos sin terminar, o None si esta sesion
                es la primera del torneo y no hay anterior
            comienzo_de_esta: Cuando empieza la sesion de la que hablamos
            ahora: La hora del servidor

        Returns:
            True si sus partidos terminaron, o si ya llego la hora de esta
        """
        if partidos_pendientes is None:
            return True
        if partidos_pendientes == 0:
            return True
        # El tope: un partido que nadie cierra no deja la siguiente colgada
        return comienzo_de_esta is not None and ahora >= comienzo_de_esta
