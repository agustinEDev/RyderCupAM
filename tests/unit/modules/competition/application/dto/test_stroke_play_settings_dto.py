"""Los DTOs de los ajustes del stroke play (#251)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.modules.competition.application.dto.competition_dto import (
    StrokePlaySettingsDTO,
    StrokePlaySettingsResponseDTO,
)


class TestLaPeticion:
    def test_una_lista_desmesurada_se_corta_antes_de_leerla_entera(self):
        with pytest.raises(ValidationError):
            StrokePlaySettingsDTO(category_limits=[Decimal("1.0")] * 21)

    def test_cinco_limites_llegan_al_dominio_para_que_diga_por_que(self):
        ajustes = StrokePlaySettingsDTO(category_limits=[Decimal("1.0")] * 5)

        assert len(ajustes.category_limits) == 5

    def test_un_contador_con_decimales_no_es_un_numero_de_categorias(self):
        with pytest.raises(ValidationError):
            StrokePlaySettingsDTO(category_count=2.5)

    def test_un_contador_fuera_de_rango_llega_al_dominio_para_que_diga_por_que(self):
        assert StrokePlaySettingsDTO(category_count=9).category_count == 9


class TestLaRespuesta:
    def test_publica_los_valores_de_la_general(self):
        esquema = StrokePlaySettingsResponseDTO.model_json_schema()

        assert set(esquema["$defs"]["OverallStanding"]["enum"]) == {"ACCUMULATED", "BEST_CARD"}

    def test_publica_el_contador_aunque_sea_vacio(self):
        respuesta = StrokePlaySettingsResponseDTO(
            category_limits=[], max_matchdays_per_player=1, overall_standing="ACCUMULATED"
        )

        assert "category_count" in respuesta.model_dump()
        assert respuesta.category_count is None
