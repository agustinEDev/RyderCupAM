"""Mirar un listado tambien abre lo que le toca (BE #331).

Hasta ahora solo abria la ficha, asi que una competicion programada seguia
apareciendo cerrada en las listas despues de su dia: anunciaba «abre el martes»
y el miercoles seguia sin dejar apuntarse.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.use_cases.list_competitions_use_case import (
    ListCompetitionsUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

MADRID = "Europe/Madrid"

pytestmark = pytest.mark.asyncio


class FakeZona:
    def __init__(self, zona: str | None = MADRID):
        self._zona = zona

    async def for_competition(self, competition: Competition) -> str | None:
        return self._zona


def _competicion(dias: int | None, empieza_en: int, visibility=Visibility.PUBLIC) -> Competition:
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
        visibility=visibility,
    )


class TestElListadoAbreLoQueToca:
    async def test_la_programada_cuya_hora_paso_sale_abierta(self):
        uow = InMemoryUnitOfWork()
        competition = _competicion(5, empieza_en=3)
        async with uow:
            await uow.competitions.add(competition)
            await uow.commit()

        use_case = ListCompetitionsUseCase(uow, zona_del_campo=FakeZona())
        resultado = await use_case.execute(viewer_id=str(uuid4()))

        assert resultado[0].status == CompetitionStatus.ACTIVE

    async def test_la_apertura_se_persiste(self):
        """No basta con devolverla abierta: el siguiente que mire la veria cerrada.

        El repositorio en memoria devuelve la MISMA instancia que guarda, asi que
        un `update` olvidado pasaria desapercibido en el assert de arriba.
        """
        uow = InMemoryUnitOfWork()
        competition = _competicion(5, empieza_en=3)
        async with uow:
            await uow.competitions.add(competition)
            await uow.commit()

        use_case = ListCompetitionsUseCase(uow, zona_del_campo=FakeZona())
        await use_case.execute(viewer_id=str(uuid4()))

        async with uow:
            guardada = await uow.competitions.find_by_id(competition.id)
        assert guardada.status == CompetitionStatus.ACTIVE

    async def test_la_que_todavia_espera_sigue_en_borrador(self):
        uow = InMemoryUnitOfWork()
        competition = _competicion(5, empieza_en=30)
        async with uow:
            await uow.competitions.add(competition)
            await uow.commit()

        use_case = ListCompetitionsUseCase(uow, zona_del_campo=FakeZona())
        resultado = await use_case.execute(viewer_id=str(uuid4()))

        assert resultado[0].status == CompetitionStatus.DRAFT

    async def test_sin_zona_no_se_abre_a_ciegas(self):
        uow = InMemoryUnitOfWork()
        competition = _competicion(5, empieza_en=3)
        async with uow:
            await uow.competitions.add(competition)
            await uow.commit()

        use_case = ListCompetitionsUseCase(uow, zona_del_campo=FakeZona(None))
        resultado = await use_case.execute(viewer_id=str(uuid4()))

        assert resultado[0].status == CompetitionStatus.DRAFT

    async def test_la_privada_de_otro_no_sale_ni_se_abre(self):
        """Lo de BE #318 sigue mandando: una privada no se anuncia a nadie."""
        uow = InMemoryUnitOfWork()
        privada = _competicion(5, empieza_en=3, visibility=Visibility.PRIVATE)
        async with uow:
            await uow.competitions.add(privada)
            await uow.commit()

        use_case = ListCompetitionsUseCase(uow, zona_del_campo=FakeZona())
        resultado = await use_case.execute(viewer_id=str(uuid4()))

        assert resultado == []

    async def test_sin_servicio_de_zona_el_listado_sigue_funcionando(self):
        """Construirlo sin la zona no puede romper el listado, solo no abrir."""
        uow = InMemoryUnitOfWork()
        competition = _competicion(5, empieza_en=3)
        async with uow:
            await uow.competitions.add(competition)
            await uow.commit()

        use_case = ListCompetitionsUseCase(uow)
        resultado = await use_case.execute(viewer_id=str(uuid4()))

        assert len(resultado) == 1
        assert resultado[0].status == CompetitionStatus.DRAFT


class TestElFiltroSeRespetaDespuesDeAbrir:
    """Abrir no puede colar en la lista algo que no cumple lo que se pidio."""

    async def test_la_que_se_abre_sale_del_filtro_de_borradores(self):
        """Si pediste DRAFT y se acaba de abrir, ya no es un borrador.

        Devolverla igual haria que una pestana «Borradores» pintase una
        competicion con las inscripciones abiertas.
        """
        uow = InMemoryUnitOfWork()
        competition = _competicion(5, empieza_en=3)
        async with uow:
            await uow.competitions.add(competition)
            await uow.commit()

        use_case = ListCompetitionsUseCase(uow, zona_del_campo=FakeZona())
        resultado = await use_case.execute(status="DRAFT", viewer_id=str(uuid4()))

        assert resultado == []
        assert competition.status == CompetitionStatus.ACTIVE

    async def test_el_filtro_se_normaliza(self):
        """`?status=active` en minusculas tiene que seguir funcionando.

        La consulta normaliza y la ruta tambien; comparar aqui en crudo traia
        las filas correctas y luego las tiraba todas.
        """
        uow = InMemoryUnitOfWork()
        competition = _competicion(None, empieza_en=30)
        competition.activate()
        async with uow:
            await uow.competitions.add(competition)
            await uow.commit()

        use_case = ListCompetitionsUseCase(uow, zona_del_campo=FakeZona())
        resultado = await use_case.execute(status="active", viewer_id=str(uuid4()))

        assert [c.id for c in resultado] == [competition.id]

    async def test_sin_filtro_salen_todas(self):
        uow = InMemoryUnitOfWork()
        competition = _competicion(5, empieza_en=3)
        async with uow:
            await uow.competitions.add(competition)
            await uow.commit()

        use_case = ListCompetitionsUseCase(uow, zona_del_campo=FakeZona())
        resultado = await use_case.execute(viewer_id=str(uuid4()))

        assert len(resultado) == 1
