"""Que una hora con huso no reviente ni cambie de significado (BE #319)."""
from datetime import date

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    UpdateCompetitionRequestDTO,
)


class TestLaHoraLlegaSinHuso:
    """El navegador manda `toISOString()`, que acaba en Z."""

    def test_una_hora_con_z_se_rechaza(self):
        """La columna es sin huso y el driver revienta con un 500."""
        with pytest.raises(ValueError):
            CreateCompetitionRequestDTO(
                name="Torneo del club",
                start_date=date(2026, 11, 1),
                end_date=date(2026, 11, 3),
                main_country="ES",
                play_mode="SCRATCH",
                enrollment_opens_at="2026-10-14T09:00:00Z",
            )

    def test_una_hora_con_desfase_tambien(self):
        """`09:00+02:00` guardado a pelo se leeria como las nueve del campo."""
        with pytest.raises(ValueError):
            UpdateCompetitionRequestDTO(enrollment_opens_at="2026-10-14T09:00:00+02:00")

    def test_la_hora_local_pasa(self):
        """Lo que se espera: la hora del campo, tal cual."""
        dto = UpdateCompetitionRequestDTO(enrollment_opens_at="2026-10-14T09:00:00")

        assert dto.enrollment_opens_at.tzinfo is None
        assert dto.enrollment_opens_at.hour == 9
