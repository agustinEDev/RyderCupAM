"""De donde sale la zona horaria de una competicion (BE #319).

Del campo donde se juega, y del primero si hay varios: la hora de apertura que
escribe el organizador es local de alli.
"""

from datetime import date

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.infrastructure.services.competition_timezone_from_course import (
    CompetitionTimezoneFromCourse,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = pytest.mark.asyncio


class CampoFalso:
    """Un campo de golf del que solo importa su zona."""

    def __init__(self, timezone: str | None):
        self.timezone = timezone


class RepositorioFalso:
    """Devuelve el campo que se le diga, por id."""

    def __init__(self, campos: dict):
        self._campos = campos

    async def find_by_id(self, golf_course_id):
        return self._campos.get(golf_course_id)


def build_competition() -> Competition:
    return Competition(
        id=CompetitionId.generate(),
        creator_id=UserId(str(CompetitionId.generate().value)),
        name=CompetitionName("Ryder Cup Madrid 2026"),
        dates=DateRange(date(2026, 6, 1), date(2026, 6, 3)),
        location=Location(CountryCode("ES")),
        team_1_name="Europe",
        team_2_name="USA",
        play_mode=PlayMode.HANDICAP,
    )


class TestTheZoneOfACompetition:
    async def test_without_a_course_there_is_no_zone(self):
        """Se puede crear, invitar y anadir el campo despues (BE #323)."""
        resolutor = CompetitionTimezoneFromCourse(RepositorioFalso({}))

        assert await resolutor.for_competition(build_competition()) is None

    async def test_it_is_the_zone_of_the_course(self):
        competition = build_competition()
        campo_id = GolfCourseId.generate()
        competition.add_golf_course(campo_id, CountryCode("ES"))
        resolutor = CompetitionTimezoneFromCourse(
            RepositorioFalso({campo_id: CampoFalso("Atlantic/Canary")})
        )

        assert await resolutor.for_competition(competition) == "Atlantic/Canary"

    async def test_with_several_it_is_the_first_one_played(self):
        """El orden es el que se juega, no el que se aparece en la base."""
        competition = build_competition()
        primero, segundo = GolfCourseId.generate(), GolfCourseId.generate()
        competition.add_golf_course(primero, CountryCode("ES"))
        competition.add_golf_course(segundo, CountryCode("ES"))
        resolutor = CompetitionTimezoneFromCourse(
            RepositorioFalso(
                {primero: CampoFalso("Europe/Madrid"), segundo: CampoFalso("Atlantic/Canary")}
            )
        )

        assert await resolutor.for_competition(competition) == "Europe/Madrid"

    async def test_a_course_without_a_zone_gives_none(self):
        """Un campo sin coordenadas no tiene zona, y no se inventa."""
        competition = build_competition()
        campo_id = GolfCourseId.generate()
        competition.add_golf_course(campo_id, CountryCode("ES"))
        resolutor = CompetitionTimezoneFromCourse(RepositorioFalso({campo_id: CampoFalso(None)}))

        assert await resolutor.for_competition(competition) is None

    async def test_a_course_that_is_not_there_does_not_bring_anything_down(self):
        """Apuntar a un campo que ya no existe se avisa, no se revienta."""
        competition = build_competition()
        competition.add_golf_course(GolfCourseId.generate(), CountryCode("ES"))
        resolutor = CompetitionTimezoneFromCourse(RepositorioFalso({}))

        assert await resolutor.for_competition(competition) is None


class RepositorioDeCompeticiones:
    """Devuelve la competición completa, como haría `find_by_id` con eager load."""

    def __init__(self, completa: Competition | None):
        self._completa = completa
        self.consultas = 0

    async def find_by_id(self, competition_id):
        self.consultas += 1
        return self._completa


class CompeticionSinCargar:
    """Imita una competición traída por el listado: tocar sus campos revienta.

    Es lo que hace SQLAlchemy cuando la relación no viene cargada y se accede a
    ella fuera de la sesión async: `MissingGreenlet`. Aquí se simula con un
    error cualquiera, porque lo que se prueba es que NO se llega a tocarla.
    """

    def __init__(self, competition: Competition):
        self.id = competition.id
        self._real = competition

    @property
    def golf_courses(self):
        raise AssertionError("no se debe tocar la relación sin cargar")


class TestCuandoLaRelacionNoVieneCargada:
    """El listado no carga los campos; la ficha sí (BE #331)."""

    async def test_la_recarga_cuando_no_esta_cargada(self, monkeypatch):
        """Sin esto, el listado reventaba con MissingGreenlet."""
        campo = GolfCourseId.generate()
        completa = _competicion_con_campo(campo)
        repo_competiciones = RepositorioDeCompeticiones(completa)
        servicio = CompetitionTimezoneFromCourse(
            RepositorioFalso({campo: CampoFalso("Europe/Madrid")}),
            repo_competiciones,
        )
        monkeypatch.setattr(
            "src.modules.competition.infrastructure.services."
            "competition_timezone_from_course.inspect",
            lambda _: type("Estado", (), {"unloaded": {"_golf_courses"}})(),
        )

        zona = await servicio.for_competition(CompeticionSinCargar(completa))

        assert zona == "Europe/Madrid"
        assert repo_competiciones.consultas == 1

    async def test_no_la_recarga_si_ya_viene_cargada(self, monkeypatch):
        """La ficha la trae entera: recargarla sería una consulta de más."""
        campo = GolfCourseId.generate()
        completa = _competicion_con_campo(campo)
        repo_competiciones = RepositorioDeCompeticiones(completa)
        servicio = CompetitionTimezoneFromCourse(
            RepositorioFalso({campo: CampoFalso("Europe/Madrid")}),
            repo_competiciones,
        )
        monkeypatch.setattr(
            "src.modules.competition.infrastructure.services."
            "competition_timezone_from_course.inspect",
            lambda _: type("Estado", (), {"unloaded": set()})(),
        )

        zona = await servicio.for_competition(completa)

        assert zona == "Europe/Madrid"
        assert repo_competiciones.consultas == 0

    async def test_sin_repositorio_de_competiciones_no_recarga(self):
        """Construido con un solo argumento se comporta como antes de BE #331."""
        campo = GolfCourseId.generate()
        completa = _competicion_con_campo(campo)
        servicio = CompetitionTimezoneFromCourse(
            RepositorioFalso({campo: CampoFalso("Europe/Madrid")})
        )

        assert await servicio.for_competition(completa) == "Europe/Madrid"


def _competicion_con_campo(golf_course_id) -> Competition:
    competition = Competition.create(
        id=CompetitionId.generate(),
        creator_id=UserId.generate(),
        name=CompetitionName("Torneo"),
        dates=DateRange(date(2026, 6, 1), date(2026, 6, 3)),
        location=Location(main_country=CountryCode("ES")),
        team_1_name="A",
        team_2_name="B",
        play_mode=PlayMode.SCRATCH,
    )
    competition.add_golf_course(golf_course_id, CountryCode("ES"))
    return competition
