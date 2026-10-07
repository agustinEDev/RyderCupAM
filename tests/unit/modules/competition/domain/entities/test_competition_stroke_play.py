"""Los ajustes del stroke play viven en la competición, en su propia pieza (#251).

Solo los tiene un Stableford o un Medal, igual que solo la Ryder tiene equipos.
Se cambian **hasta que la competición empieza** (DRAFT, ACTIVE y CLOSED), la misma
ventana que el hándicap personalizado: de ellos sale la categoría que se fija al
empezar.
"""

from datetime import date
from decimal import Decimal

import pytest

from src.modules.competition.domain.entities.competition import (
    Competition,
    CompetitionStateError,
    TournamentTypeError,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.overall_standing import OverallStanding
from src.modules.competition.domain.value_objects.stroke_play_setup import (
    StrokePlaySettingsError,
)
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode

TRES_DIAS = DateRange(date(2030, 6, 5), date(2030, 6, 7))


def _stroke_play(tipo=TournamentType.STABLEFORD, status=CompetitionStatus.DRAFT, **extra):
    return Competition(
        id=CompetitionId.generate(),
        creator_id=UserId.generate(),
        name=CompetitionName("Medal de octubre"),
        dates=TRES_DIAS,
        location=Location(CountryCode("ES")),
        play_mode=PlayMode.HANDICAP,
        tournament_type=tipo,
        status=status,
        **extra,
    )


def _ryder(**extra):
    return Competition(
        id=CompetitionId.generate(),
        creator_id=UserId.generate(),
        name=CompetitionName("Ryder de los amigos"),
        dates=TRES_DIAS,
        location=Location(CountryCode("ES")),
        play_mode=PlayMode.HANDICAP,
        team_1_name="Europa",
        team_2_name="América",
        **extra,
    )


class TestAlCrear:
    @pytest.mark.parametrize("tipo", [TournamentType.STABLEFORD, TournamentType.MEDAL])
    def test_un_stroke_play_sin_ajustes_tiene_los_de_por_defecto(self, tipo):
        competicion = _stroke_play(tipo)

        assert competicion.stroke_play is not None
        assert competicion.stroke_play.category_limits == ()
        assert competicion.stroke_play.max_matchdays_per_player == 1
        assert competicion.stroke_play.overall_standing is OverallStanding.ACCUMULATED

    def test_un_medal_con_dos_limites(self):
        competicion = _stroke_play(
            TournamentType.MEDAL, category_limits=[Decimal("12.0"), Decimal("26.0")]
        )

        assert competicion.stroke_play.number_of_categories == 3

    def test_una_ryder_no_tiene_la_pieza(self):
        assert _ryder().stroke_play is None

    @pytest.mark.parametrize(
        "ajuste",
        [
            {"category_limits": [Decimal("12.0")]},
            {"category_limits": []},
            {"max_matchdays_per_player": 1},
            {"overall_standing": OverallStanding.ACCUMULATED},
        ],
    )
    def test_una_ryder_con_cualquier_ajuste_de_stroke_play_se_rechaza(self, ajuste):
        with pytest.raises(TournamentTypeError, match="Una Ryder Cup no tiene categorías"):
            _ryder(**ajuste)

    def test_mas_jornadas_por_jugador_que_dias_de_torneo_se_rechaza(self):
        with pytest.raises(StrokePlaySettingsError, match="4 jornadas.*3 días"):
            _stroke_play(max_matchdays_per_player=4)

    def test_tantas_jornadas_como_dias_vale(self):
        assert _stroke_play(max_matchdays_per_player=3).stroke_play.max_matchdays_per_player == 3


class TestAlCambiar:
    @pytest.mark.parametrize("status", [CompetitionStatus.DRAFT, CompetitionStatus.ACTIVE])
    def test_hasta_que_se_cierran_las_inscripciones_se_puede_cambiar(self, status):
        competicion = _stroke_play(status=status)

        competicion.update_stroke_play(category_limits=[Decimal("18.0")])

        assert competicion.stroke_play.category_limits == (Decimal("18.0"),)

    @pytest.mark.parametrize(
        "status",
        [
            CompetitionStatus.CLOSED,
            CompetitionStatus.IN_PROGRESS,
            CompetitionStatus.COMPLETED,
            CompetitionStatus.CANCELLED,
        ],
    )
    def test_con_las_inscripciones_cerradas_ya_no(self, status):
        """Al cerrar se fija el hándicap de cada uno y su categoría (7 oct)."""
        competicion = _stroke_play(status=status)

        with pytest.raises(CompetitionStateError, match="hasta que se cierran las inscripciones"):
            competicion.update_stroke_play(category_limits=[Decimal("18.0")])

    def test_cambiar_un_ajuste_deja_los_otros(self):
        competicion = _stroke_play(
            category_limits=[Decimal("12.0")], overall_standing=OverallStanding.BEST_CARD
        )

        competicion.update_stroke_play(max_matchdays_per_player=2)

        assert competicion.stroke_play.category_limits == (Decimal("12.0"),)
        assert competicion.stroke_play.overall_standing is OverallStanding.BEST_CARD
        assert competicion.stroke_play.max_matchdays_per_player == 2

    def test_una_lista_vacia_quita_las_categorias(self):
        competicion = _stroke_play(category_limits=[Decimal("12.0")])

        competicion.update_stroke_play(category_limits=[])

        assert competicion.stroke_play.category_limits == ()

    def test_mas_jornadas_que_dias_se_rechaza_tambien_al_cambiar(self):
        competicion = _stroke_play()

        with pytest.raises(StrokePlaySettingsError):
            competicion.update_stroke_play(max_matchdays_per_player=4)

    def test_a_una_ryder_no_se_le_cambian(self):
        with pytest.raises(TournamentTypeError, match="Una Ryder Cup no tiene categorías"):
            _ryder().update_stroke_play(category_limits=[Decimal("12.0")])


class TestLasFechasNoDejanFueraLasJornadas:
    def test_acortar_el_torneo_por_debajo_de_las_jornadas_se_rechaza(self):
        competicion = _stroke_play(max_matchdays_per_player=3)

        with pytest.raises(StrokePlaySettingsError, match="3 jornadas.*2 días"):
            competicion.update_info(dates=DateRange(date(2030, 6, 5), date(2030, 6, 6)))

        assert competicion.dates == TRES_DIAS

    def test_acortarlo_sin_bajar_de_las_jornadas_vale(self):
        competicion = _stroke_play(max_matchdays_per_player=2)

        competicion.update_info(dates=DateRange(date(2030, 6, 5), date(2030, 6, 6)))

        assert competicion.dates.end_date == date(2030, 6, 6)

    def test_a_una_ryder_las_fechas_le_dan_igual(self):
        competicion = _ryder()

        competicion.update_info(dates=DateRange(date(2030, 6, 5), date(2030, 6, 5)))

        assert competicion.dates.end_date == date(2030, 6, 5)

    def test_si_las_fechas_no_valen_no_cambia_nada_mas(self):
        """La competición no puede quedar a medias: ni el nombre cambia."""
        competicion = _stroke_play(max_matchdays_per_player=3)
        nombre = competicion.name

        with pytest.raises(StrokePlaySettingsError):
            competicion.update_info(
                name=CompetitionName("Otro nombre"),
                dates=DateRange(date(2030, 6, 5), date(2030, 6, 5)),
            )

        assert competicion.name == nombre


class TestCuandoSeTocaElHandicap:
    """Stroke play: hasta cerrar inscripciones. Ryder: como siempre, hasta empezar."""

    @pytest.mark.parametrize(
        "status, se_puede",
        [
            (CompetitionStatus.DRAFT, True),
            (CompetitionStatus.ACTIVE, True),
            (CompetitionStatus.CLOSED, False),
            (CompetitionStatus.IN_PROGRESS, False),
        ],
    )
    def test_stroke_play(self, status, se_puede):
        assert _stroke_play(status=status).allows_handicap_edits() is se_puede

    @pytest.mark.parametrize(
        "status, se_puede",
        [
            (CompetitionStatus.ACTIVE, True),
            (CompetitionStatus.CLOSED, True),
            (CompetitionStatus.IN_PROGRESS, False),
        ],
    )
    def test_ryder(self, status, se_puede):
        assert _ryder(status=status).allows_handicap_edits() is se_puede
