"""
Tests de ScoringOpeningService — a que hora se puede empezar a anotar (BE #305).

La anotacion de un partido se abre sola a una hora fija segun la sesion de su
ronda, en la zona horaria de la competicion. Lo que decide es el reloj del
servidor cuando llega el golpe, nunca una hora enviada por el cliente.
"""

from datetime import UTC, date, datetime

import pytest

from src.modules.competition.domain.services.scoring_opening_service import (
    ScoringOpeningService,
)
from src.modules.competition.domain.value_objects.session_type import SessionType

MADRID = "Europe/Madrid"
CANARIAS = "Atlantic/Canary"


class TestHoraDeApertura:
    """Que hora abre cada sesion, en la zona de la competicion."""

    @pytest.mark.parametrize(
        ("session_type", "hora"),
        [
            (SessionType.MORNING, 6),
            (SessionType.AFTERNOON, 12),
            (SessionType.EVENING, 18),
        ],
    )
    def test_cada_sesion_abre_a_su_hora(self, session_type, hora):
        abre = ScoringOpeningService.opens_at(date(2026, 9, 20), session_type, MADRID)

        assert abre is not None
        assert (abre.year, abre.month, abre.day) == (2026, 9, 20)
        assert (abre.hour, abre.minute) == (hora, 0)
        assert abre.utcoffset() is not None, "la hora se devuelve con su desfase, no suelta"

    def test_es_la_hora_local_de_la_competicion_no_la_del_servidor(self):
        """Las seis de Canarias no son las seis de Madrid: una hora de diferencia."""
        madrid = ScoringOpeningService.opens_at(date(2026, 9, 20), SessionType.MORNING, MADRID)
        canarias = ScoringOpeningService.opens_at(date(2026, 9, 20), SessionType.MORNING, CANARIAS)

        assert madrid.astimezone(UTC) == datetime(2026, 9, 20, 4, 0, tzinfo=UTC)
        assert canarias.astimezone(UTC) == datetime(2026, 9, 20, 5, 0, tzinfo=UTC)

    def test_el_horario_de_invierno_tambien_cuenta(self):
        """En enero Madrid va una hora por delante de UTC, no dos."""
        abre = ScoringOpeningService.opens_at(date(2026, 1, 20), SessionType.MORNING, MADRID)

        assert abre.astimezone(UTC) == datetime(2026, 1, 20, 5, 0, tzinfo=UTC)

    @pytest.mark.parametrize(
        ("round_date", "session_type"),
        [
            (None, SessionType.MORNING),
            (date(2026, 9, 20), None),
            (None, None),
        ],
    )
    def test_sin_fecha_o_sin_sesion_no_hay_apertura(self, round_date, session_type):
        """Rondas viejas: no se abren solas, siguen necesitando START."""
        assert ScoringOpeningService.opens_at(round_date, session_type, MADRID) is None

    def test_una_zona_que_no_existe_no_tumba_la_lectura(self):
        """
        La entidad valida la zona al crearse, asi que llegar aqui con una mala
        significa que el dato entro por otro sitio. Devolver None deja el partido
        sin apertura automatica —START sigue— en vez de romper la vista de
        anotacion y el calendario, que llaman a esto para pintarse.
        """
        assert (
            ScoringOpeningService.opens_at(date(2026, 9, 20), SessionType.MORNING, "Marte/Olympus")
            is None
        )

    def test_una_sesion_desconocida_tampoco(self):
        """Datos raros no pueden tumbar la vista de anotacion ni el calendario."""
        assert ScoringOpeningService.opens_at(date(2026, 9, 20), "MADRUGADA", MADRID) is None
