"""
Tests de la zona horaria de una competicion (BE #305).

La anotacion se abre a una hora LOCAL del campo, asi que la competicion tiene
que saber en que zona se juega. No se puede deducir del pais: la tabla de paises
no guarda husos, y un pais puede tener varios (España peninsular y Canarias).
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.competition import (
    DEFAULT_TIMEZONE,
    Competition,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode


def _crear(**kwargs) -> Competition:
    return Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=UserId(str(uuid4())),
        name=CompetitionName("Torneo de prueba"),
        dates=DateRange(start_date=date(2026, 6, 1), end_date=date(2026, 6, 3)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_1_name="Equipo A",
        team_2_name="Equipo B",
        **kwargs,
    )


class TestZonaHoraria:
    def test_por_defecto_es_madrid(self):
        """Lo que juega hoy la aplicacion es España peninsular."""
        assert _crear().timezone == DEFAULT_TIMEZONE
        assert DEFAULT_TIMEZONE == "Europe/Madrid"

    def test_se_puede_crear_en_otra_zona(self):
        assert _crear(timezone="Atlantic/Canary").timezone == "Atlantic/Canary"

    def test_una_zona_que_no_existe_no_se_guarda(self):
        """Guardarla abriria la anotacion a una hora que no es la del campo."""
        with pytest.raises(ValueError, match="zona"):
            _crear(timezone="Marte/Olympus")

    def test_tampoco_vacia(self):
        with pytest.raises(ValueError, match="zona"):
            _crear(timezone="")
