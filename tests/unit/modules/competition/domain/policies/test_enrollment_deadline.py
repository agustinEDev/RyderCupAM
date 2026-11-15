"""
El plazo de inscripción: las 12:00 del día anterior al torneo (15 nov 2026).

| Caso | Regla                                                                  |
|------|------------------------------------------------------------------------|
| C1   | Cierra a las 12:00 del día ANTERIOR a `start_date`, hora del campo     |
| C1   | Sin campo (o con una zona que no existe), hora de Europe/Madrid        |
| C1   | La hora se le pone al día con la zona: no se convierte                 |
| C1   | Un reloj sin zona se lee en UTC, como las fechas que se guardan        |
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.modules.competition.domain.policies.enrollment_deadline import (
    ZONA_SIN_CAMPO,
    closes_at,
    has_passed,
)

TORNEO = date(2026, 11, 20)


class TestCuandoCierra:
    def test_a_las_doce_del_dia_anterior_en_la_zona_del_campo(self):
        """
        C1. Given un torneo que empieza el 20 en un campo de Madrid
        When se pregunta cuándo cierra
        Then el 19 a las 12:00 de Madrid
        """
        assert closes_at(TORNEO, "Europe/Madrid") == datetime(
            2026, 11, 19, 12, 0, tzinfo=ZoneInfo("Europe/Madrid")
        )

    def test_en_canarias_es_una_hora_mas_tarde_en_utc(self):
        """
        C1. Given el mismo torneo en un campo de Canarias
        When se compara con el de Madrid
        Then cierra una hora más tarde: las 12:00 son las de allí
        """
        madrid = closes_at(TORNEO, "Europe/Madrid")
        canarias = closes_at(TORNEO, "Atlantic/Canary")

        assert canarias - madrid == timedelta(hours=1)
        assert canarias.astimezone(UTC) == datetime(2026, 11, 19, 12, 0, tzinfo=UTC)

    def test_sin_campo_manda_la_hora_de_madrid(self):
        """C1. Given una competición sin campo (zona None) / Then las 12:00 de Madrid."""
        assert ZONA_SIN_CAMPO == "Europe/Madrid"
        assert closes_at(TORNEO, None) == closes_at(TORNEO, "Europe/Madrid")

    def test_una_zona_que_no_existe_tampoco_tumba_nada(self):
        """C1. Given un campo con una zona que no existe / Then la de Madrid, sin error."""
        assert closes_at(TORNEO, "Marte/Olympus") == closes_at(TORNEO, "Europe/Madrid")

    def test_en_verano_tambien_son_las_doce_de_alli(self):
        """C1. Given un torneo en julio (horario de verano) / Then las 10:00 UTC del día anterior."""
        cierre = closes_at(date(2026, 7, 10), "Europe/Madrid")

        assert cierre.astimezone(UTC) == datetime(2026, 7, 9, 10, 0, tzinfo=UTC)


class TestSiYaPaso:
    @pytest.mark.parametrize(
        ("ahora", "pasado"),
        [
            (datetime(2026, 11, 19, 10, 59, 59, tzinfo=UTC), False),
            # Las 12:00 de Madrid en noviembre son las 11:00 UTC: justo ahí, cerrado
            (datetime(2026, 11, 19, 11, 0, tzinfo=UTC), True),
            (datetime(2026, 11, 19, 11, 0, 1, tzinfo=UTC), True),
            (datetime(2026, 11, 25, 9, 0, tzinfo=UTC), True),
        ],
    )
    def test_desde_las_doce_en_punto(self, ahora, pasado):
        """
        C1. Given el torneo del 20 en Madrid
        When el reloj está antes, justo en, o después de las 12:00 del 19
        Then solo antes sigue abierto
        """
        assert has_passed(TORNEO, "Europe/Madrid", ahora) is pasado

    def test_un_reloj_sin_zona_es_utc(self):
        """C1. Given un instante sin zona (como los guardados) / Then se lee en UTC."""
        assert has_passed(TORNEO, "Europe/Madrid", datetime(2026, 11, 19, 10, 59)) is False
        assert has_passed(TORNEO, "Europe/Madrid", datetime(2026, 11, 19, 11, 0)) is True
