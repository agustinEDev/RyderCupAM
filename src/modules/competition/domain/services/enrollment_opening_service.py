"""
A que hora se abren solas las inscripciones de una competicion (BE #319, #332).

Un torneo entre amigos no programa nada: nace con las inscripciones abiertas.
Un club si: se crea hoy y las inscripciones abren cinco dias antes de jugarse.

Lo que el organizador dice son **dias de antelacion**, no una fecha: «abre cinco
dias antes». El instante no se guarda, se deriva en cada lectura a partir de la
fecha de inicio del torneo, de modo que mover las fechas mueve la apertura sin
que nadie tenga que acordarse (decidido el 21 sep).

La hora es **las 00:00 del campo donde se juega**: «cinco dias completos antes»
sale literal y no hay que inventarse ninguna hora. La zona sale de las
coordenadas del campo, nunca del pais: tres puntos espanoles dan `Europe/Madrid`,
`Atlantic/Canary` y `Africa/Ceuta` (BE #305).

Sin campo todavia, o con un campo cuya zona no se conoce, no hay hora que
calcular y el torneo **no se abre solo**. No se adivina: abrir a deshora anuncia
una cosa y hace otra.
"""

import logging
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)


class EnrollmentOpeningService:
    """Calcula a que hora abren las inscripciones, y si ya abrieron."""

    @staticmethod
    def opens_at(
        start_date: date | None, days_before: int | None, timezone: str | None
    ) -> datetime | None:
        """
        El instante en que abren, con su desfase.

        Args:
            start_date: El dia en que empieza a jugarse el torneo.
            days_before: Cuantos dias antes abren las inscripciones, 1 a 14.
                `None` significa que no hay apertura programada.
            timezone: La zona IANA del primer campo que se juega.

        Returns:
            El instante con su huso, o `None` si no hay nada que calcular.
        """
        if start_date is None or days_before is None or timezone is None:
            return None

        try:
            zone = ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            # Una zona que no existe no puede tumbar la LECTURA: esto se llama
            # al pintar la pantalla de la competicion. Sin hora, el torneo no se
            # abre solo, que es justo lo que se quiere cuando no se sabe cuando
            logger.warning("Zona horaria desconocida al calcular la apertura: %s", timezone)
            return None

        dia = start_date - timedelta(days=days_before)

        # Las 00:00 se le PONEN al dia con el huso del campo, no se convierten:
        # convertirlas las moveria al huso de quien mira.
        #
        # Casi todas las zonas cambian la hora de madrugada, a las 2 o las 3, y
        # entonces las 00:00 no tienen nada de particular. Pero no todas: en
        # Santiago de Chile o en La Habana el reloj salta de las 23:59 a la
        # 1:00, y esa medianoche NO EXISTE en el calendario. `fold=0`, que es el
        # comportamiento por defecto, la resuelve en el mismo instante que
        # habria tenido sin el salto —el reloj local lo ensena como la 1:00—.
        # Se acepta a proposito: abrir una hora mas tarde ese dia concreto es
        # inofensivo, y dejar el torneo sin abrir por un cambio de hora, no.
        return datetime.combine(dia, time(0, 0), tzinfo=zone)

    @staticmethod
    def is_due(
        start_date: date | None, days_before: int | None, timezone: str | None
    ) -> bool:
        """
        Indica si ya paso la hora de abrir.

        Quien lo decide es el reloj del SERVIDOR, comparando instantes en UTC.
        Si lo decidiera el cliente, cambiarle la hora al movil abriria el
        torneo antes de tiempo.
        """
        abre = EnrollmentOpeningService.opens_at(start_date, days_before, timezone)
        if abre is None:
            return False
        return abre <= datetime.now(UTC)
