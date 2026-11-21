"""
El savepoint del UoW en memoria deshace TODO lo escrito dentro (CodeRabbit en la #534).

Las partidas, las plazas, las esperas y las actualizaciones de hándicap faltaban
en la copia: un fallo dentro las dejaba escritas a medias en los tests. Y al
reponer, cada repositorio sigue viendo a los demás vivos (CodeRabbit en la #916:
el de barras por campo mira las inscripciones del mismo UoW).
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.espera_en_franja import EsperaEnFranja
from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.jugador_de_partida import (
    JugadorDePartida,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


async def test_a_failure_inside_undoes_groups_places_and_waits():
    uow = InMemoryUnitOfWork()
    competicion, franja = CompetitionId(uuid4()), RoundId.generate()
    ahora = datetime(2030, 10, 1, tzinfo=UTC)
    jugadores = [
        JugadorDePartida(
            UserId.generate(), Decimal("0.0"), 0, TeeColor.YELLOW, None, (0,) * 18, (4,) * 18
        )
        for _ in range(2)
    ]

    with pytest.raises(RuntimeError):
        async with uow.savepoint():
            partida = Partida.crear(competicion, franja, 1, jugadores)
            await uow.partidas.anadir([partida])
            await uow.golpes_de_partida.guardar(
                GolpeDePartida.crear(
                    partida.id, franja, competicion, jugadores[0].user_id, 1, ahora
                )
            )
            await uow.plazas.add(PlazaEnFranja.crear(competicion, franja, UserId.generate(), ahora))
            await uow.esperas.add(
                EsperaEnFranja.crear(competicion, franja, UserId.generate(), ahora)
            )
            raise RuntimeError("falla dentro")

    assert await uow.partidas.de_la_franja(franja) == []
    assert await uow.golpes_de_partida.de_la_franja(franja) == []
    assert await uow.plazas.de_la_franja(franja) == []
    assert await uow.esperas.de_la_competicion(competicion) == []


async def test_a_failure_inside_keeps_the_course_tees_looking_at_the_live_enrollments():
    """
    Given un savepoint que falla dentro
    When después se inscribe a alguien y se le fija una barra propia en un campo
    Then las barras por campo la ven: siguen mirando las inscripciones vivas del
        UoW, no una copia de antes del savepoint
    """
    uow = InMemoryUnitOfWork()
    competicion, campo = CompetitionId(uuid4()), GolfCourseId(uuid4())

    with pytest.raises(RuntimeError):
        async with uow.savepoint():
            raise RuntimeError("falla dentro")

    inscripcion = Enrollment(
        id=EnrollmentId.generate(),
        competition_id=competicion,
        user_id=UserId.generate(),
        status=EnrollmentStatus.APPROVED,
    )
    await uow.enrollments.add(inscripcion)
    await uow.barras_por_campo.fijar_propia(inscripcion, campo, TeeColor.BLUE)

    assert (await uow.barras_por_campo.del_campo(competicion, campo)).propias == {
        inscripcion.user_id: TeeColor.BLUE
    }
