"""A que hora se abren solas las inscripciones (BE #319).

Dos maneras de arrancar un torneo, y ninguna es pulsar un boton:

- **Entre amigos**: no hay fecha, y la primera invitacion lo abre (BE #319a).
- **Club**: se crea hoy y las inscripciones abren el miercoles a las nueve. Se
  pone la fecha, y se abre sola.

«Las nueve» son las nueve **del campo donde se juega**, que es lo que el
organizador tiene en la cabeza al escribirlo. La zona sale de las coordenadas
del campo, no del pais: tres puntos espanoles dan `Europe/Madrid`,
`Atlantic/Canary` y `Africa/Ceuta` (BE #305).

Y quien decide que ya es la hora es el SERVIDOR. Si lo decidiera el movil,
cambiarle el reloj abriria el torneo antes de tiempo.

Sin campo todavia, o con un campo sin zona conocida, **no se abre sola**:
decidido el 20 sep, no se adivina. Ahi sigue abriendo la invitacion.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.modules.competition.domain.services.enrollment_opening_service import (
    EnrollmentOpeningService,
)

MADRID = "Europe/Madrid"
CANARIAS = "Atlantic/Canary"


class TestWhenItOpens:
    """La hora escrita, leida en la zona del campo."""

    def test_the_hour_is_read_at_the_course(self):
        """Las nueve en Madrid y las nueve en Canarias no son el mismo instante."""
        escrito = datetime(2026, 10, 14, 9, 0)

        en_madrid = EnrollmentOpeningService.opens_at(escrito, MADRID)
        en_canarias = EnrollmentOpeningService.opens_at(escrito, CANARIAS)

        assert en_madrid == datetime(2026, 10, 14, 9, 0, tzinfo=ZoneInfo(MADRID))
        assert en_canarias == datetime(2026, 10, 14, 9, 0, tzinfo=ZoneInfo(CANARIAS))
        assert en_canarias > en_madrid

    def test_without_a_date_there_is_no_hour(self):
        """Sin fecha manda la invitacion, no el reloj."""
        assert EnrollmentOpeningService.opens_at(None, MADRID) is None

    def test_without_a_zone_there_is_no_hour(self):
        """Sin campo, o con un campo sin zona: no se adivina."""
        assert EnrollmentOpeningService.opens_at(datetime(2026, 10, 14, 9, 0), None) is None

    def test_an_unknown_zone_does_not_bring_anything_down(self):
        """Una zona que no existe no puede tumbar la lectura de la pantalla."""
        assert EnrollmentOpeningService.opens_at(datetime(2026, 10, 14, 9, 0), "Marte/Olympus") is None


class TestWhetherItIsDue:
    """Si ya toca abrir, con el reloj del servidor."""

    def test_an_hour_already_past_is_due(self):
        hace_una_hora = datetime.now(ZoneInfo(MADRID)) - timedelta(hours=1)

        assert EnrollmentOpeningService.is_due(hace_una_hora.replace(tzinfo=None), MADRID) is True

    def test_an_hour_still_to_come_is_not(self):
        dentro_de_una_hora = datetime.now(ZoneInfo(MADRID)) + timedelta(hours=1)

        assert EnrollmentOpeningService.is_due(dentro_de_una_hora.replace(tzinfo=None), MADRID) is False

    @pytest.mark.parametrize("zona", [None, "Marte/Olympus"])
    def test_without_a_usable_zone_it_is_never_due(self, zona):
        """Nunca se abre a ciegas: sin zona, el torneo espera al campo."""
        hace_una_hora = datetime.now(UTC) - timedelta(hours=1)

        assert EnrollmentOpeningService.is_due(hace_una_hora.replace(tzinfo=None), zona) is False

    def test_the_canary_hour_has_not_arrived_when_the_madrid_one_has(self):
        """La misma hora escrita, dos campos: en uno toca y en el otro todavia no.

        Justo en esa hora de diferencia esta el sentido de leerla en el campo:
        con la zona equivocada, el torneo canario abriria una hora antes de lo
        que su organizador anuncio.
        """
        ahora_en_madrid = datetime.now(ZoneInfo(MADRID)).replace(tzinfo=None)

        assert EnrollmentOpeningService.is_due(ahora_en_madrid, MADRID) is True
        assert EnrollmentOpeningService.is_due(ahora_en_madrid, CANARIAS) is False
