"""El rango de dias de antelacion, en la puerta de entrada (BE #332).

Sustituye a los tests del huso: cuando la apertura era una fecha y una hora,
habia que rechazar las que llegaban con zona —`toISOString()` acaba en `Z`—.
Un entero no tiene ese problema; lo que hay que sujetar ahora es el rango.
"""

from datetime import date

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    UpdateCompetitionRequestDTO,
)


def _crear(dias):
    return CreateCompetitionRequestDTO(
        name="Ryder Cup 2026",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 3),
        main_country="ES",
        play_mode="SCRATCH",
        enrollment_opens_days_before=dias,
    )


class TestElRangoEnLaEntrada:
    """1 a 14, y nada mas. El DTO lo rechaza antes de llegar al dominio."""

    @pytest.mark.parametrize("dias", [1, 7, 14])
    def test_acepta_lo_que_esta_dentro(self, dias):
        assert _crear(dias).enrollment_opens_days_before == dias

    def test_sin_programar_es_lo_normal(self):
        assert _crear(None).enrollment_opens_days_before is None

    @pytest.mark.parametrize("dias", [0, 15, -1])
    def test_rechaza_lo_que_esta_fuera(self, dias):
        with pytest.raises(ValueError):
            _crear(dias)

    def test_al_editar_tambien(self):
        """La edicion es la otra puerta, y se olvidaba en BE #313."""
        with pytest.raises(ValueError):
            UpdateCompetitionRequestDTO(enrollment_opens_days_before=15)

    def test_al_editar_null_desprograma(self):
        """`None` explicito quita la apertura, no significa «dejala como esta»."""
        dto = UpdateCompetitionRequestDTO(enrollment_opens_days_before=None)

        assert "enrollment_opens_days_before" in dto.model_fields_set
