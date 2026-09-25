"""
El nombre de quien invita, como aparece en ESA competición (#710).

    #   caso                                         | nombre
    ----|---------------------------------------------|------------------
    Q1  inscrito, sin pedir nada (por defecto)      | el legal (BE #254)
    Q2  inscrito, pidió su alias en ella            | el alias
    Q3  no inscrito (un admin que invita)           | el de siempre: alias
    Q4  ya no existe                                | «Unknown»
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.services.nombre_de_quien_invita import (
    nombre_de_quien_invita,
    quieren_su_nombre_legal,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


class _Usuario:
    """Con alias, para ver cuál de los dos nombres sale."""

    def display_name_or_legal(self, legal: bool) -> str:
        return "Agustin Estevez" if legal else "Trinx"


async def _inscrito(uow, competicion, jugador, *, alias_aqui: bool = False):
    inscripcion = Enrollment.direct_enroll(
        id=EnrollmentId.generate(), competition_id=competicion, user_id=jugador
    )
    if alias_aqui:
        inscripcion.set_name_preference(use_real_name=False)
    async with uow:
        await uow.enrollments.add(inscripcion)


async def _nombre(uow, competicion, jugador) -> str:
    async with uow:
        legales = await quieren_su_nombre_legal(uow, [(competicion, jugador)])
    return nombre_de_quien_invita(_Usuario(), (competicion, jugador) in legales)


async def test_q1_inscrito_sin_pedir_nada_sale_su_nombre_legal():
    uow, competicion, jugador = InMemoryUnitOfWork(), CompetitionId(uuid4()), UserId(uuid4())
    await _inscrito(uow, competicion, jugador)

    assert await _nombre(uow, competicion, jugador) == "Agustin Estevez"


async def test_q2_si_pidio_su_alias_en_ella_sale_el_alias():
    uow, competicion, jugador = InMemoryUnitOfWork(), CompetitionId(uuid4()), UserId(uuid4())
    await _inscrito(uow, competicion, jugador, alias_aqui=True)

    assert await _nombre(uow, competicion, jugador) == "Trinx"


async def test_q3_sin_inscripcion_sale_su_nombre_de_siempre():
    uow, competicion, jugador = InMemoryUnitOfWork(), CompetitionId(uuid4()), UserId(uuid4())

    assert await _nombre(uow, competicion, jugador) == "Trinx"


def test_q4_si_ya_no_existe_se_dice():
    assert nombre_de_quien_invita(None, True) == "Unknown"


async def test_q5_una_consulta_por_competicion_no_por_invitacion():
    """Una página de invitaciones puede traer 100: una consulta por cada una eran
    100 viajes a la base de datos (CodeRabbit en la #381)."""
    uow, competicion = InMemoryUnitOfWork(), CompetitionId(uuid4())
    jugadores = [UserId(uuid4()) for _ in range(3)]
    await _inscrito(uow, competicion, jugadores[0])
    await _inscrito(uow, competicion, jugadores[1], alias_aqui=True)
    lotes = AsyncMock(wraps=uow.enrollments.find_by_user_ids_and_competition)
    uow.enrollments.find_by_user_ids_and_competition = lotes
    uno_a_uno = AsyncMock(wraps=uow.enrollments.find_by_user_and_competition)
    uow.enrollments.find_by_user_and_competition = uno_a_uno

    async with uow:
        legales = await quieren_su_nombre_legal(uow, [(competicion, j) for j in jugadores])

    assert legales == {(competicion, jugadores[0])}
    assert lotes.await_count == 1
    uno_a_uno.assert_not_awaited()
