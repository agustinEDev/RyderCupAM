"""
La lectura bloqueada de una inscripción (21 oct, revisión de la solicitud al empezar).

Aprobar leía la solicitud antes de bloquear la competición: si la competición
empezaba entre medias, la aprobaba aunque ya estuviera rechazada. Ahora decide
con la inscripción releída con su fila bloqueada. En memoria no se ve: no hay
transacciones.
"""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.enrollment_repository import (
    SQLAlchemyEnrollmentRepository,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_match_repository_for_update import (  # noqa: F401
    BASE_DATE,
    _esta_bloqueada,
    creator_id,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _solicitud(db_session, creator_id) -> Enrollment:  # noqa: F811
    competition = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creator_id,
        name=CompetitionName(f"Solicitudes {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=1)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_1_name="Team A",
        team_2_name="Team B",
    )
    await SQLAlchemyCompetitionRepository(db_session).add(competition)
    # El jugador es el propio creador: la fila de usuario ya existe
    solicitud = Enrollment.request(
        id=EnrollmentId.generate(), competition_id=competition.id, user_id=creator_id
    )
    await SQLAlchemyEnrollmentRepository(db_session).add(solicitud)
    await db_session.commit()
    db_session.expunge_all()
    return solicitud


async def test_bloquea_la_fila_de_la_inscripcion(db_session, creator_id):  # noqa: F811
    creada = await _solicitud(db_session, creator_id)

    leida = await SQLAlchemyEnrollmentRepository(db_session).find_by_id_for_update(creada.id)

    assert leida.id == creada.id
    assert await _esta_bloqueada(db_session, "enrollments", creada.id.value) is True


async def test_trae_el_estado_de_la_base_de_datos_no_el_que_ya_tenia(
    db_session,
    creator_id,  # noqa: F811
):
    """Sin forzar la relectura, la sesión devolvía el objeto que ya tenía, con el
    estado de ANTES: se aprobaba una solicitud que el arranque ya había rechazado."""
    creada = await _solicitud(db_session, creator_id)
    repo = SQLAlchemyEnrollmentRepository(db_session)
    vieja = await repo.find_by_id(creada.id)
    assert vieja.status.value == "REQUESTED"
    # Otra conexión la rechaza y confirma
    async with db_session.bind.begin() as conn:
        await conn.execute(
            text("UPDATE enrollments SET status = 'REJECTED' WHERE id = :id"),
            {"id": str(creada.id.value)},
        )

    releida = await repo.find_by_id_for_update(creada.id)

    assert releida.status.value == "REJECTED"


async def test_si_no_existe_devuelve_none(db_session):
    repo = SQLAlchemyEnrollmentRepository(db_session)

    assert await repo.find_by_id_for_update(EnrollmentId.generate()) is None
