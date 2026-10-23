"""
Cuándo se cierra sola una partida rápida que nadie termina (Agustín, 23 oct 2026).

| Caso | Partida                                         | Se cierra                          |
|------|-------------------------------------------------|------------------------------------|
| B1   | En juego, empezada el sáb 18 a las 9:00 (Meis)  | lun 20 a las 00:00 hora del campo  |
| B2   | Empezada el sábado a las 23:50                  | también el lunes a las 00:00       |
| B2   | Empezada el domingo a las 00:30 (sáb en UTC)    | el martes: cuenta el día del campo |
|      | Cambio de hora (sáb 24 oct)                     | lun 26 a las 00:00 de invierno     |
| B3   | Sin `started_at` (de antes)                     | con su `created_at`                |
| B4   | PENDING                                         | a los 7 días de crearse            |
| B8   | Campo sin zona horaria                          | en UTC                             |
|      | Terminada o cancelada                           | nunca                              |
| B12  | Cerrada hasta 2 días tarde                      | se publica en Actividad            |
| B12  | Cerrada más de 2 días tarde                     | no se publica                      |
"""

from datetime import datetime, timedelta

import pytest

from src.modules.quick_match.domain.services.quick_match_closing import (
    closes_at,
    publishes_when_closed,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus

MADRID = "Europe/Madrid"
EN_JUEGO = QuickMatchStatus.IN_PROGRESS


def _cierra(status=EN_JUEGO, created_at=None, started_at=None, timezone=MADRID):
    return closes_at(
        status=status,
        created_at=created_at or datetime(2026, 10, 18, 6, 0),
        started_at=started_at,
        timezone=timezone,
    )


class TestInProgress:
    def test_b1_at_the_end_of_the_next_day_in_the_course_time(self):
        # Sábado 18 a las 9:00 en Madrid son las 7:00 UTC; el lunes 20 a las
        # 00:00 en Madrid, las 22:00 UTC del domingo
        assert _cierra(started_at=datetime(2026, 10, 18, 7, 0)) == datetime(2026, 10, 19, 22, 0)

    def test_b2_started_just_before_midnight(self):
        assert _cierra(started_at=datetime(2026, 10, 18, 21, 50)) == datetime(2026, 10, 19, 22, 0)

    def test_b2_the_day_is_the_courses_not_utcs(self):
        # Domingo a las 00:30 en Madrid es todavía sábado en UTC
        assert _cierra(started_at=datetime(2026, 10, 18, 22, 30)) == datetime(2026, 10, 20, 22, 0)

    def test_across_the_change_of_time(self):
        # Sábado 24 (verano, +2) -> lunes 26 a las 00:00 de invierno (+1)
        assert _cierra(started_at=datetime(2026, 10, 24, 8, 0)) == datetime(2026, 10, 25, 23, 0)

    def test_b3_without_a_start_it_counts_from_its_creation(self):
        assert _cierra(created_at=datetime(2026, 10, 18, 7, 0)) == datetime(2026, 10, 19, 22, 0)

    def test_b8_a_course_without_time_zone_closes_in_utc(self):
        assert _cierra(started_at=datetime(2026, 10, 18, 23, 0), timezone=None) == datetime(
            2026, 10, 20, 0, 0
        )


class TestTheOthers:
    def test_b4_a_pending_one_after_seven_days(self):
        creada = datetime(2026, 10, 16, 18, 30)

        assert _cierra(status=QuickMatchStatus.PENDING, created_at=creada) == creada + timedelta(
            days=7
        )

    @pytest.mark.parametrize("status", [QuickMatchStatus.COMPLETED, QuickMatchStatus.CANCELLED])
    def test_a_finished_one_never(self, status):
        assert _cierra(status=status, started_at=datetime(2026, 10, 18, 7, 0)) is None


class TestPublishing:
    CIERRA = datetime(2026, 10, 19, 22, 0)

    @pytest.mark.parametrize(
        ("ahora", "publica"),
        [
            (CIERRA, True),
            (CIERRA + timedelta(days=2), True),
            (CIERRA + timedelta(days=2, seconds=1), False),
        ],
    )
    def test_b12_only_if_it_is_not_more_than_two_days_late(self, ahora, publica):
        assert publishes_when_closed(self.CIERRA, ahora) is publica
