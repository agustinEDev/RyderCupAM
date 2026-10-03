"""
Los campos de una competición están en sus países, también al cambiarlos.

El país de un campo solo se comprobaba al añadirlo. Al editar la ubicación no:
una competición pasada de España a Francia se quedaba con su campo de España.
Decidido por Agustín el 3 oct 2026: se rechaza, con el motivo, y los campos se
quitan antes desde la ficha.

Los campos son otro agregado: el caso de uso trae sus países y la regla vive
aquí, como con los capitanes.
"""

from datetime import date

import pytest

from src.modules.competition.domain.entities.competition import (
    Competition,
    GolfCoursesOutsideLocationError,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode

ES, FR, PT = CountryCode("ES"), CountryCode("FR"), CountryCode("PT")


def _competicion(location: Location) -> Competition:
    competicion = Competition.create(
        id=CompetitionId.generate(),
        creator_id=UserId.generate(),
        name=CompetitionName("Torneo del club"),
        dates=DateRange(date(2030, 6, 1), date(2030, 6, 2)),
        location=location,
        play_mode=PlayMode.HANDICAP,
        team_1_name="Europa",
        team_2_name="América",
    )
    competicion.activate()
    return competicion


def test_l1_cambiar_de_pais_con_un_campo_del_anterior_no_se_puede():
    competicion = _competicion(Location(ES))

    with pytest.raises(GolfCoursesOutsideLocationError, match="ES"):
        competicion.update_info(location=Location(FR), golf_course_countries=[ES])


def test_l2_si_el_anterior_queda_como_adyacente_si():
    competicion = _competicion(Location(ES))

    competicion.update_info(location=Location(FR, ES), golf_course_countries=[ES])

    assert competicion.location.main_country == FR


def test_l2b_vale_tambien_como_segundo_adyacente():
    competicion = _competicion(Location(ES))

    competicion.update_info(location=Location(FR, PT, ES), golf_course_countries=[ES])

    assert competicion.location.adjacent_country_2 == ES


def test_l3_quitar_un_adyacente_que_tiene_campos_no_se_puede():
    competicion = _competicion(Location(ES, PT))

    with pytest.raises(GolfCoursesOutsideLocationError, match="PT"):
        competicion.update_info(location=Location(ES), golf_course_countries=[ES, PT])


def test_l4_sin_campos_se_cambia_sin_mas():
    competicion = _competicion(Location(ES))

    competicion.update_info(location=Location(FR), golf_course_countries=[])

    assert competicion.location.main_country == FR


def test_l5_cambiar_la_ubicacion_exige_decir_los_paises_de_los_campos():
    """Que nadie pueda saltarse la comprobación olvidando pasarlos."""
    competicion = _competicion(Location(ES))

    with pytest.raises(ValueError, match="países de sus campos"):
        competicion.update_info(location=Location(FR))


def test_l6_lo_demas_no_los_necesita():
    competicion = _competicion(Location(ES))

    competicion.update_info(name=CompetitionName("Otro nombre"))

    assert str(competicion.name) == "Otro Nombre"


def test_el_error_es_un_valueerror():
    """La API ya traduce ValueError a 400 al editar."""
    assert issubclass(GolfCoursesOutsideLocationError, ValueError)
