"""
A que hora se abren solas las inscripciones de una competicion (BE #319).

Un torneo entre amigos no programa nada: se invita a alguien y con eso se abre.
Un club sí: se crea hoy y las inscripciones abren el miercoles a las nueve.

«Las nueve» son las nueve **del campo donde se juega** — es lo que el
organizador tiene en la cabeza al escribirlo, y es lo que decidio Agustin el 20
sep. La zona sale de las coordenadas del campo, nunca del pais: tres puntos
espanoles dan `Europe/Madrid`, `Atlantic/Canary` y `Africa/Ceuta`, asi que el
pais no la determina (BE #305).

Sin campo todavia, o con un campo cuya zona no se conoce, no hay hora que
calcular y el torneo **no se abre solo**. No se adivina: abrir a deshora
anuncia una cosa y hace otra. Ahi sigue abriendo la invitacion.
"""

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)


class EnrollmentOpeningService:
    """Calcula a que hora abren las inscripciones, y si ya abrieron."""

    @staticmethod
    def opens_at(enrollment_opens_at: datetime | None, timezone: str | None) -> datetime | None:
        """
        El instante en que abren, con su desfase.

        Args:
            enrollment_opens_at: La fecha y hora que escribio el organizador,
                sin huso: es hora local del campo.
            timezone: La zona IANA del primer campo que se juega.

        Returns:
            El instante con su huso, o `None` si no hay nada que calcular.
        """
        if enrollment_opens_at is None or timezone is None:
            return None

        try:
            zone = ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            # Una zona que no existe no puede tumbar la LECTURA: esto se llama
            # al pintar la pantalla de la competicion. Sin hora, el torneo no se
            # abre solo, que es justo lo que se quiere cuando no se sabe cuando
            logger.warning("Zona horaria desconocida al calcular la apertura: %s", timezone)
            return None

        # La hora que escribio el organizador ya es local: se le pone el huso,
        # no se convierte. Convertirla la moveria al huso de quien la mira.
        #
        # La madrugada del cambio de hora, una hora del calendario puede existir
        # dos veces —en Madrid, las 2:30 del 25 de octubre— o no existir —el 29
        # de marzo se salta de las 2:00 a las 3:00—. `fold=0`, que es el
        # comportamiento por defecto, resuelve las dos como hace falta aqui: la
        # ambigua se queda con la PRIMERA pasada (abre antes, no despues), y la
        # que no existe cae en el mismo instante que habria tenido sin el salto,
        # que el reloj local muestra como las 3:30. No se rechaza ninguna de las
        # dos: son horas legitimas del calendario, y quien escribe «2:30» no
        # tiene por que saberse los cambios de hora de memoria
        return enrollment_opens_at.replace(tzinfo=zone)

    @staticmethod
    def is_due(enrollment_opens_at: datetime | None, timezone: str | None) -> bool:
        """
        Indica si ya paso la hora de abrir.

        Quien lo decide es el reloj del SERVIDOR, comparando instantes en UTC.
        Si lo decidiera el cliente, cambiarle la hora al movil abriria el
        torneo antes de tiempo.
        """
        abre = EnrollmentOpeningService.opens_at(enrollment_opens_at, timezone)
        if abre is None:
            return False
        return abre <= datetime.now(UTC)
