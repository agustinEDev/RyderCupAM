"""EnrollmentOpener: abrir una competición programada, en un solo sitio (BE #331)."""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.services.enrollment_opener import EnrollmentOpener
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

MADRID = "Europe/Madrid"

pytestmark = pytest.mark.asyncio


class FakeZona:
    """Devuelve la zona que se le diga, o None si la competición no tiene campo."""

    def __init__(self, zona: str | None):
        self._zona = zona
        self.consultas = 0

    async def for_competition(self, competition: Competition) -> str | None:
        self.consultas += 1
        return self._zona


def _competicion(dias: int | None, empieza_en: int) -> Competition:
    empieza = date.today() + timedelta(days=empieza_en)
    return Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=UserId(uuid4()),
        name=CompetitionName("Torneo del club"),
        dates=DateRange(empieza, empieza + timedelta(days=2)),
        location=Location(main_country="ES"),
        team_1_name="A",
        team_2_name="B",
        play_mode=PlayMode.SCRATCH,
        enrollment_opens_days_before=dias,
    )


async def _guardar(uow: InMemoryUnitOfWork, *competitions: Competition) -> None:
    async with uow:
        for c in competitions:
            await uow.competitions.add(c)
        await uow.commit()


class TestAbrirLasQueToquen:
    async def test_abre_la_que_ya_paso_su_hora(self):
        """Empieza en 3 días y abría 5 antes: hace dos que le tocaba."""
        uow, zona = InMemoryUnitOfWork(), FakeZona(MADRID)
        competition = _competicion(5, empieza_en=3)
        await _guardar(uow, competition)

        async with uow:
            await EnrollmentOpener.abrir_las_que_toquen([competition], uow, zona)

        assert competition.status == CompetitionStatus.ACTIVE

    async def test_deja_la_que_todavia_espera(self):
        uow, zona = InMemoryUnitOfWork(), FakeZona(MADRID)
        competition = _competicion(5, empieza_en=30)
        await _guardar(uow, competition)

        async with uow:
            await EnrollmentOpener.abrir_las_que_toquen([competition], uow, zona)

        assert competition.status == CompetitionStatus.DRAFT

    async def test_sin_zona_espera_en_vez_de_adivinar(self):
        """Sin campo no hay zona, y abrir a deshora anuncia una cosa y hace otra."""
        uow, zona = InMemoryUnitOfWork(), FakeZona(None)
        competition = _competicion(5, empieza_en=3)
        await _guardar(uow, competition)

        async with uow:
            await EnrollmentOpener.abrir_las_que_toquen([competition], uow, zona)

        assert competition.status == CompetitionStatus.DRAFT

    async def test_abre_unas_y_deja_otras(self):
        """Un listado trae de todo: solo se abre lo que le toca."""
        uow, zona = InMemoryUnitOfWork(), FakeZona(MADRID)
        toca = _competicion(5, empieza_en=3)
        espera = _competicion(5, empieza_en=30)
        sin_programar = _competicion(None, empieza_en=10)
        await _guardar(uow, toca, espera, sin_programar)

        async with uow:
            await EnrollmentOpener.abrir_las_que_toquen(
                [toca, espera, sin_programar], uow, zona
            )

        assert toca.status == CompetitionStatus.ACTIVE
        assert espera.status == CompetitionStatus.DRAFT
        assert sin_programar.status == CompetitionStatus.DRAFT

    async def test_no_resuelve_la_zona_de_quien_no_la_necesita(self):
        """La zona cuesta una consulta por competición: es lo último que se pregunta.

        Un listado trae hasta 100, y casi ninguna programa su apertura. Resolver
        la zona de todas sería el N+1 que BE #330 ya tuvo que arreglar una vez.
        """
        uow, zona = InMemoryUnitOfWork(), FakeZona(MADRID)
        sin_programar = [_competicion(None, empieza_en=10) for _ in range(5)]
        await _guardar(uow, *sin_programar)

        async with uow:
            await EnrollmentOpener.abrir_las_que_toquen(sin_programar, uow, zona)

        assert zona.consultas == 0

    async def test_sin_servicio_de_zona_no_hace_nada(self):
        """El caso de uso puede construirse sin él: entonces no abre nada."""
        uow = InMemoryUnitOfWork()
        competition = _competicion(5, empieza_en=3)
        await _guardar(uow, competition)

        async with uow:
            await EnrollmentOpener.abrir_las_que_toquen([competition], uow, None)

        assert competition.status == CompetitionStatus.DRAFT


class TestLoQueNiSiquieraSeMira:
    """La zona cuesta una consulta: lo que no es candidato no llega a pedirla."""

    async def test_una_cancelada_con_dias_no_resuelve_la_zona(self):
        """Cancelar NO borra los dias, al contrario que abrir.

        Sin esta guarda, una competicion cancelada que tenia apertura programada
        se queda con los dias puestos para siempre y paga la consulta de la zona
        en cada listado, para acabar descartandose igual.
        """
        uow, zona = InMemoryUnitOfWork(), FakeZona(MADRID)
        competition = _competicion(5, empieza_en=3)
        competition.cancel()
        await _guardar(uow, competition)

        async with uow:
            await EnrollmentOpener.abrir_las_que_toquen([competition], uow, zona)

        assert zona.consultas == 0
        assert competition.status == CompetitionStatus.CANCELLED
