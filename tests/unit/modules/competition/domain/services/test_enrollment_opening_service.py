"""Tests de la apertura derivada de los dias de antelacion (BE #332)."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from src.modules.competition.domain.services.enrollment_opening_service import (
    EnrollmentOpeningService,
)


class TestOpensAt:
    """`opens_at` deriva el instante de la fecha de inicio y los dias."""

    def test_cuenta_los_dias_hacia_atras_desde_el_comienzo(self):
        """Cinco dias antes del 10 de junio es el 5, a las 00:00 del campo."""
        abre = EnrollmentOpeningService.opens_at(date(2026, 6, 10), 5, "Europe/Madrid")

        assert abre == datetime(2026, 6, 5, 0, 0, tzinfo=ZoneInfo("Europe/Madrid"))

    def test_un_dia_antes_es_la_vispera(self):
        """El minimo, 1, abre el dia anterior al torneo."""
        abre = EnrollmentOpeningService.opens_at(date(2026, 6, 10), 1, "Europe/Madrid")

        assert abre.date() == date(2026, 6, 9)

    def test_catorce_dias_antes_cruza_el_mes(self):
        """El maximo, 14, restando por encima del cambio de mes."""
        abre = EnrollmentOpeningService.opens_at(date(2026, 6, 10), 14, "Europe/Madrid")

        assert abre.date() == date(2026, 5, 27)

    def test_sin_dias_no_hay_nada_que_calcular(self):
        """La mayoria de torneos no programan nada: ahi manda la invitacion."""
        assert EnrollmentOpeningService.opens_at(date(2026, 6, 10), None, "Europe/Madrid") is None

    def test_sin_zona_espera_en_vez_de_adivinar(self):
        """Sin campo todavia no hay zona, y abrir a deshora anuncia otra cosa."""
        assert EnrollmentOpeningService.opens_at(date(2026, 6, 10), 5, None) is None

    def test_una_zona_que_no_existe_no_tumba_la_lectura(self):
        """Esto se llama al pintar la pantalla: no puede reventar."""
        assert EnrollmentOpeningService.opens_at(date(2026, 6, 10), 5, "Marte/Olympus") is None

    def test_la_zona_es_la_del_campo_no_la_del_servidor(self):
        """Las 00:00 de Canarias no son las de Madrid: una hora de diferencia."""
        madrid = EnrollmentOpeningService.opens_at(date(2026, 6, 10), 5, "Europe/Madrid")
        canarias = EnrollmentOpeningService.opens_at(date(2026, 6, 10), 5, "Atlantic/Canary")

        assert madrid.utcoffset() != canarias.utcoffset()
        assert canarias > madrid

    def test_una_medianoche_que_no_existe_no_revienta(self):
        """Hay zonas donde el cambio de hora se come las 00:00.

        En Santiago de Chile el reloj salta de las 23:59 del sabado a la 1:00
        del domingo, asi que las 00:00 de ese dia no existen en el calendario.
        No es motivo para dejar el torneo sin abrir: `fold=0` lo resuelve en el
        instante que habria tenido sin el salto, y el reloj local lo ensena como
        la 1:00. Abrir una hora mas tarde ese dia concreto es inofensivo;
        quedarse sin abrir, no.
        """
        abre = EnrollmentOpeningService.opens_at(date(2026, 9, 11), 5, "America/Santiago")

        # El instante en UTC es lo unico que prueba donde cayo de verdad: la
        # fecha de pared seria la misma aunque el calculo estuviera mal, porque
        # `combine` guarda el dia que se le da pase lo que pase con el huso.
        # Las 00:00 inexistentes del 6 caen en el instante que habrian tenido
        # sin el salto, que alli se lee como la 1:00
        assert abre.astimezone(UTC) == datetime(2026, 9, 6, 4, 0, tzinfo=UTC)
        # Y ese instante, leido en el reloj del campo, son la 1:00 — hay que
        # pasar por UTC para verlo: `astimezone` sobre un datetime que ya lleva
        # esa zona no lo normaliza y devolveria las 00:00 que no existieron
        en_el_campo = abre.astimezone(UTC).astimezone(ZoneInfo("America/Santiago"))
        assert en_el_campo.hour == 1


class TestIsDue:
    """`is_due` lo decide el reloj del servidor, nunca el del movil."""

    def test_ya_paso_la_hora(self):
        ayer = date.today()
        assert EnrollmentOpeningService.is_due(ayer, 1, "Europe/Madrid") is True

    def test_todavia_no_toca(self):
        # Con timedelta y no `replace(year=...)`: el 29 de febrero de un bisiesto
        # ese replace revienta con «day is out of range for month»
        dentro_de_un_mes = date.today() + timedelta(days=30)
        assert EnrollmentOpeningService.is_due(dentro_de_un_mes, 1, "Europe/Madrid") is False

    def test_sin_dias_nunca_toca(self):
        assert EnrollmentOpeningService.is_due(date(2020, 1, 1), None, "Europe/Madrid") is False

    def test_sin_zona_nunca_toca(self):
        """Nunca se abre a ciegas: sin campo, el torneo espera."""
        assert EnrollmentOpeningService.is_due(date(2020, 1, 1), 5, None) is False

    def test_el_instante_lleva_huso_para_poder_compararlo_en_utc(self):
        """Si saliera sin huso, `is_due` reventaria al compararlo con `now(UTC)`.

        Es lo que hace que decida el reloj del SERVIDOR y no el del movil: se
        comparan instantes, no horas de calendario.
        """
        abre = EnrollmentOpeningService.opens_at(date(2026, 6, 10), 5, "Europe/Madrid")

        assert abre.tzinfo is not None
        assert abre.utcoffset() is not None
