"""
El tipo de torneo vive en la competición (RyderCupAM#251).

Decidido el 1 oct 2026: modalidad → tipo. Los equipos, el modo de montaje y lo
que cuelga de ellos (capitanes, draft, sobres) son cosa del tipo Ryder Cup, y
viven en su pieza, `RyderCupSetup`. Un Stableford o un Medal no la tiene, y
pedírsela es un error que se dice, no un dato que se tira en silencio.
"""

from datetime import date

import pytest

from src.modules.competition.domain.entities.competition import (
    Competition,
    TournamentTypeError,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.setup_mode import SetupMode
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.modality import Modality
from src.shared.domain.value_objects.play_mode import PlayMode

STROKE_PLAY = [TournamentType.STABLEFORD, TournamentType.MEDAL]


def _base(**extra) -> dict:
    argumentos = {
        "id": CompetitionId.generate(),
        "creator_id": UserId.generate(),
        "name": CompetitionName("Torneo del club"),
        "dates": DateRange(date(2030, 6, 1), date(2030, 6, 3)),
        "location": Location(CountryCode("ES")),
        "play_mode": PlayMode.HANDICAP,
    }
    argumentos.update(extra)
    return argumentos


def _ryder(**extra) -> Competition:
    return Competition(**_base(team_1_name="Europa", team_2_name="América", **extra))


def _stroke(tipo=TournamentType.STABLEFORD, **extra) -> Competition:
    return Competition(**_base(tournament_type=tipo, **extra))


class TestUnaCompeticionSinTipo:
    def test_es_ryder_cup_como_todas_las_de_hoy(self):
        competicion = _ryder()

        assert competicion.tournament_type == TournamentType.RYDER_CUP
        assert competicion.modality == Modality.MATCH_PLAY

    def test_conserva_su_pieza_de_ryder_cup(self):
        ryder = _ryder().ryder_cup

        assert (ryder.team_1_name, ryder.team_2_name) == ("Europa", "América")
        assert ryder.setup_mode == SetupMode.RYDER_CUP
        assert ryder.team_assignment == TeamAssignment.MANUAL

    def test_el_factory_tambien_la_hace_ryder_cup(self):
        competicion = Competition.create(**_base(team_1_name="Europa", team_2_name="América"))

        assert competicion.tournament_type == TournamentType.RYDER_CUP

    def test_el_modo_de_montaje_se_sigue_eligiendo(self):
        assert _ryder(setup_mode=SetupMode.AUTOMATIC).ryder_cup.setup_mode == SetupMode.AUTOMATIC


class TestUnaRyderCup:
    def test_sin_nombres_de_equipo_no_se_crea(self):
        """Lo de siempre: una Ryder sin equipos no es una Ryder."""
        with pytest.raises(ValueError):
            Competition(**_base(tournament_type=TournamentType.RYDER_CUP))

    def test_require_ryder_cup_devuelve_su_pieza(self):
        competicion = _ryder()

        assert competicion.require_ryder_cup() is competicion.ryder_cup


class TestUnTorneoDeStrokePlay:
    @pytest.mark.parametrize("tipo", STROKE_PLAY)
    def test_se_crea_sin_pieza_de_ryder_cup(self, tipo):
        competicion = _stroke(tipo)

        assert competicion.tournament_type == tipo
        assert competicion.modality == Modality.STROKE_PLAY
        assert competicion.ryder_cup is None

    def test_el_factory_crea_un_stableford(self):
        competicion = Competition.create(**_base(tournament_type=TournamentType.STABLEFORD))

        assert competicion.tournament_type == TournamentType.STABLEFORD
        assert competicion.ryder_cup is None

    @pytest.mark.parametrize(
        "equipos",
        [
            {"team_1_name": "Europa", "team_2_name": "América"},
            {"team_1_name": "Europa"},
            {"team_2_name": "América"},
        ],
    )
    def test_con_nombres_de_equipo_no_se_crea(self, equipos):
        """No se tiran en silencio: quien los manda cree que existen."""
        with pytest.raises(TournamentTypeError, match="equipos"):
            _stroke(**equipos)

    @pytest.mark.parametrize("modo", list(SetupMode))
    def test_con_modo_de_montaje_no_se_crea(self, modo):
        with pytest.raises(TournamentTypeError, match="montaje"):
            _stroke(setup_mode=modo)

    def test_con_reparto_de_equipos_no_se_crea(self):
        with pytest.raises(TournamentTypeError, match="equipos"):
            _stroke(team_assignment=TeamAssignment.AUTOMATIC)

    def test_el_error_es_un_valueerror(self):
        """La API ya traduce ValueError a 400 al crear: no hace falta otra ruta."""
        assert issubclass(TournamentTypeError, ValueError)

    @pytest.mark.parametrize("tipo", STROKE_PLAY)
    def test_require_ryder_cup_dice_por_que(self, tipo):
        with pytest.raises(TournamentTypeError, match=f"Un {tipo.label} no tiene equipos"):
            _stroke(tipo).require_ryder_cup()

    @pytest.mark.parametrize(
        "cambio",
        [
            {"team_1_name": "Europa"},
            {"team_2_name": "América"},
            {"setup_mode": SetupMode.AUTOMATIC},
            {"team_assignment": TeamAssignment.AUTOMATIC},
        ],
    )
    def test_no_se_le_ponen_equipos_al_editarlo(self, cambio):
        with pytest.raises(TournamentTypeError):
            _stroke().update_info(**cambio)

    def test_lo_demas_se_edita_como_siempre(self):
        competicion = _stroke()

        competicion.update_info(name=CompetitionName("Stableford de otoño"))

        assert str(competicion.name) == "Stableford De Otoño"
        assert competicion.ryder_cup is None

    def test_la_baja_de_un_jugador_no_toca_capitanes(self):
        """
        No hay capitanes que ascender: no cambia nada. Con las inscripciones
        abiertas, que es cuando una Ryder sí miraría a sus capitanes.
        """
        competicion = _stroke()
        competicion.activate()

        assert competicion.handle_withdrawal(UserId.generate()) is False


class TestLosCapitanesSonDeLaRyderCup:
    """Viven en la entidad, así que es ella la que se niega, no cada caso de uso."""

    def test_nombrar_capitanes(self):
        with pytest.raises(TournamentTypeError):
            _stroke().name_captains(
                UserId.generate(), UserId.generate(), approved_player_ids=[], has_teams=False
            )

    def test_nombrar_vicecapitan(self):
        with pytest.raises(TournamentTypeError):
            _stroke().name_vice_captain("A", UserId.generate(), team_player_ids=[], has_teams=False)

    def test_cubrir_un_capitan(self):
        with pytest.raises(TournamentTypeError):
            _stroke().fill_captain("A", UserId.generate(), team_player_ids=[], has_teams=False)

    def test_repartir_equipos(self):
        with pytest.raises(TournamentTypeError):
            _stroke().teams_reassigned()
