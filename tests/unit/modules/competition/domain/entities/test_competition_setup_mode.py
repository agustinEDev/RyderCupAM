"""
El modo de configuración vive en la competición (FE #695).

Se elige al crearla y se puede cambiar **mientras las inscripciones sigan
abiertas**; al cerrarlas queda fijo, porque de ahí en adelante decide lo que ya
está montado. Esa es exactamente la regla que ya usa `update_info`.
"""

from datetime import date

import pytest

from src.modules.competition.domain.entities.competition import (
    Competition,
    CompetitionStateError,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.setup_mode import SetupMode
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode


def _competicion(**extra) -> Competition:
    argumentos = {
        "id": CompetitionId.generate(),
        "creator_id": UserId.generate(),
        "name": CompetitionName("Ryder de los amigos"),
        "dates": DateRange(date(2030, 6, 1), date(2030, 6, 3)),
        "location": Location(CountryCode("ES")),
        "team_1_name": "Europa",
        "team_2_name": "América",
        "play_mode": PlayMode.HANDICAP,
    }
    argumentos.update(extra)
    return Competition(**argumentos)


class TestSetupModeEnLaCompeticion:
    def test_nace_en_estilo_rydercup(self):
        """Es lo que son hoy todas: equipos, capitanes y calendario a mano o mixto."""
        assert _competicion().setup_mode == SetupMode.RYDER_CUP

    @pytest.mark.parametrize("modo", list(SetupMode))
    def test_se_elige_al_crearla(self, modo):
        assert _competicion(setup_mode=modo).setup_mode == modo

    @pytest.mark.parametrize(
        "estado", [CompetitionStatus.DRAFT, CompetitionStatus.ACTIVE]
    )
    def test_se_cambia_mientras_las_inscripciones_siguen_abiertas(self, estado):
        competicion = _competicion(status=estado)

        competicion.update_info(setup_mode=SetupMode.AUTOMATIC)

        assert competicion.setup_mode == SetupMode.AUTOMATIC

    @pytest.mark.parametrize(
        "estado",
        [
            CompetitionStatus.CLOSED,
            CompetitionStatus.IN_PROGRESS,
            CompetitionStatus.COMPLETED,
            CompetitionStatus.CANCELLED,
        ],
    )
    def test_cerradas_las_inscripciones_ya_no_se_cambia(self, estado):
        """De ahí en adelante decide lo que ya está montado."""
        competicion = _competicion(status=estado, setup_mode=SetupMode.MANUAL)

        with pytest.raises(CompetitionStateError):
            competicion.update_info(setup_mode=SetupMode.AUTOMATIC)

        assert competicion.setup_mode == SetupMode.MANUAL

    def test_editar_otra_cosa_no_lo_toca(self):
        """`None` es «no lo cambies», como el resto de campos de `update_info`."""
        competicion = _competicion(setup_mode=SetupMode.AUTOMATIC)

        competicion.update_info(name=CompetitionName("Otro nombre"))

        assert competicion.setup_mode == SetupMode.AUTOMATIC


class TestSetupModeAlCrearla:
    """Por el factory, que es por donde pasa el caso de uso de verdad."""

    def _crear(self, **extra) -> Competition:
        return Competition.create(
            id=CompetitionId.generate(),
            creator_id=UserId.generate(),
            name=CompetitionName("Ryder de los amigos"),
            dates=DateRange(date(2030, 6, 1), date(2030, 6, 3)),
            location=Location(CountryCode("ES")),
            team_1_name="Europa",
            team_2_name="América",
            play_mode=PlayMode.HANDICAP,
            **extra,
        )

    def test_sin_decir_nada_nace_en_estilo_rydercup(self):
        assert self._crear().setup_mode == SetupMode.RYDER_CUP

    @pytest.mark.parametrize("modo", list(SetupMode))
    def test_con_el_modo_elegido(self, modo):
        assert self._crear(setup_mode=modo).setup_mode == modo


class TestElModoMandaSobreElReparto:
    """Decidido el 22 sep: el reparto de equipos deja de preguntarse aparte.

    Antes había un campo propio (`team_assignment`) que podía contradecir al
    modo: «todo automático» con el reparto a mano. Ahora sale del modo.
    """

    @pytest.mark.parametrize(
        ("modo", "reparto"),
        [
            (SetupMode.AUTOMATIC, TeamAssignment.AUTOMATIC),
            (SetupMode.MANUAL, TeamAssignment.MANUAL),
            # En estilo RyderCup los equipos salen del draft, o se ponen a mano:
            # lo que no puede es repartirlos la app a espaldas del organizador
            (SetupMode.RYDER_CUP, TeamAssignment.MANUAL),
        ],
    )
    def test_al_crearla_el_reparto_sale_del_modo(self, modo, reparto):
        competicion = _competicion(setup_mode=modo, team_assignment=TeamAssignment.AUTOMATIC)

        assert competicion.team_assignment == reparto

    def test_cambiar_el_modo_cambia_el_reparto(self):
        competicion = _competicion(setup_mode=SetupMode.MANUAL)

        competicion.update_info(setup_mode=SetupMode.AUTOMATIC)

        assert competicion.team_assignment == TeamAssignment.AUTOMATIC

    def test_el_modo_gana_aunque_lleguen_los_dos(self):
        competicion = _competicion(setup_mode=SetupMode.MANUAL)

        competicion.update_info(
            setup_mode=SetupMode.AUTOMATIC, team_assignment=TeamAssignment.MANUAL
        )

        assert competicion.team_assignment == TeamAssignment.AUTOMATIC

    def test_sin_tocar_el_modo_el_reparto_se_respeta(self):
        """Editar otra cosa no puede cambiarle el reparto por debajo."""
        competicion = _competicion(setup_mode=SetupMode.RYDER_CUP)

        competicion.update_info(team_assignment=TeamAssignment.AUTOMATIC)

        assert competicion.team_assignment == TeamAssignment.AUTOMATIC

