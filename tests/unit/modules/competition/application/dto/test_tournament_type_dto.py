"""
El tipo de torneo en la API (RyderCupAM#251).

El frontend de hoy no manda tipo: tiene que seguir creando exactamente la Ryder
de siempre, con sus valores por defecto. Un Stableford o un Medal no recibe
esos valores: si los mandara el cliente, los rechaza la entidad con su motivo.
"""

from datetime import date

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.domain.value_objects.setup_mode import SetupMode
from src.modules.competition.domain.value_objects.tournament_type import TournamentType


def _peticion(**extra) -> CreateCompetitionRequestDTO:
    datos = {
        "name": "Torneo del club",
        "start_date": date(2030, 6, 1),
        "end_date": date(2030, 6, 2),
        "main_country": "ES",
        "play_mode": "HANDICAP",
    }
    datos.update(extra)
    return CreateCompetitionRequestDTO(**datos)


class TestSinTipo:
    def test_es_una_ryder_cup_con_los_valores_de_siempre(self):
        peticion = _peticion()

        assert peticion.tournament_type == TournamentType.RYDER_CUP
        assert (peticion.team_1_name, peticion.team_2_name) == ("Team 1", "Team 2")
        assert peticion.team_assignment == "MANUAL"
        assert peticion.setup_mode == SetupMode.RYDER_CUP

    def test_lo_que_manda_el_cliente_manda(self):
        peticion = _peticion(team_1_name="Europa", setup_mode="AUTOMATIC")

        assert peticion.team_1_name == "Europa"
        assert peticion.setup_mode == SetupMode.AUTOMATIC


class TestStrokePlay:
    def test_no_recibe_nada_de_la_ryder(self):
        peticion = _peticion(tournament_type="STABLEFORD")

        assert peticion.tournament_type == TournamentType.STABLEFORD
        assert peticion.team_1_name is None
        assert peticion.team_2_name is None
        assert peticion.team_assignment is None
        assert peticion.setup_mode is None

    def test_lo_que_manda_el_cliente_llega_para_que_lo_rechace_el_dominio(self):
        """No se tira aquí: se le dice a quien lo manda por qué no vale."""
        peticion = _peticion(tournament_type="MEDAL", team_1_name="Europa")

        assert peticion.team_1_name == "Europa"
