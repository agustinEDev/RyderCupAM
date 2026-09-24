"""
Pedir plaza en una pública, de verdad contra la API (BE #372).

Lo que un test unitario no ve: que el día del torneo la ruta deja pasar, y que
los «no» llegan como 400 con su motivo y no como un 500, que el navegador toma
por un fallo de red (sin cabeceras de CORS) y deja al jugador sin respuesta.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.services.competition_policy import (
    MAX_ENROLLMENTS_PER_USER,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.enrollment_repository import (
    SQLAlchemyEnrollmentRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from tests.conftest import _URL_DE_LA_BD_DE_TEST
from tests.integration.api.v1.helpers.auth_helper import create_and_login_user

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _jugador(client: AsyncClient, nombre: str):
    _, cookies = await create_and_login_user(
        client,
        email=f"{nombre}_{uuid4()}@test.com",
        password="SecurePass123!",
        first_name=nombre.capitalize(),
        last_name="Club",
    )
    return cookies


async def _publica(client: AsyncClient, empieza: date, max_players: int = 12):
    organiza = await _jugador(client, "organiza")
    creada = await client.post(
        "/api/v1/competitions",
        json={
            "name": f"Club {uuid4().hex[:6]}",
            "start_date": empieza.isoformat(),
            "end_date": (empieza + timedelta(days=1)).isoformat(),
            "main_country": "ES",
            "play_mode": "SCRATCH",
            "max_players": max_players,
            "visibility": "PUBLIC",
        },
        cookies=organiza,
    )
    assert creada.status_code == 201, creada.text
    return creada.json()["id"], organiza


async def _pide(client: AsyncClient, competicion_id: str, cookies):
    return await client.post(
        f"/api/v1/competitions/{competicion_id}/enrollments",
        json={"type": "REQUEST"},
        cookies=cookies,
    )


async def test_el_dia_del_torneo_se_pide_plaza(client: AsyncClient):
    competicion_id, _ = await _publica(client, date.today())

    respuesta = await _pide(client, competicion_id, await _jugador(client, "tarde"))

    assert respuesta.status_code == 201, respuesta.text


async def test_empezado_el_torneo_es_un_400_con_el_motivo(client: AsyncClient):
    competicion_id, _ = await _publica(client, date.today())
    engine = create_async_engine(_URL_DE_LA_BD_DE_TEST["url"])
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE competitions SET start_date = :d WHERE id = :id"),
                {"d": date.today() - timedelta(days=1), "id": competicion_id},
            )
    finally:
        await engine.dispose()

    respuesta = await _pide(client, competicion_id, await _jugador(client, "tarde"))

    assert respuesta.status_code == 400, respuesta.text
    assert "ya ha empezado" in respuesta.json()["detail"]


async def test_llena_es_un_400_con_el_motivo(client: AsyncClient):
    competicion_id, organiza = await _publica(
        client, date.today() + timedelta(days=5), max_players=2
    )
    # El organizador ya ocupa una plaza: con otro aprobado, se llena
    otro = await _pide(client, competicion_id, await _jugador(client, "otro"))
    assert otro.status_code == 201, otro.text
    aprobado = await client.post(
        f"/api/v1/enrollments/{otro.json()['id']}/approve", cookies=organiza
    )
    assert aprobado.status_code == 200, aprobado.text

    respuesta = await _pide(client, competicion_id, await _jugador(client, "ultimo"))

    assert respuesta.status_code == 400, respuesta.text
    assert "completa" in respuesta.json()["detail"]


async def test_con_el_maximo_de_inscripciones_es_un_400_con_el_motivo(client: AsyncClient):
    """Sin esto, quitar el 400 de la ruta no lo cazaba nada (CodeRabbit en la #373).

    Las veinte en las que ya está van directas a la base de datos: por la API
    chocan con sus límites por hora, que no son lo que se prueba aquí.
    """
    usuario, cookies = await create_and_login_user(
        client,
        email=f"maximo_{uuid4()}@test.com",
        password="SecurePass123!",
        first_name="Maximo",
        last_name="Club",
    )
    quien = UserId(str(usuario["id"]))
    organizador = UserId(str(uuid4()))
    engine = create_async_engine(_URL_DE_LA_BD_DE_TEST["url"])
    try:
        async with AsyncSession(engine) as sesion:
            await sesion.execute(
                text(
                    "INSERT INTO users (id, first_name, last_name, email, password, created_at, "
                    "updated_at, email_verified, failed_login_attempts, is_admin) VALUES "
                    "(:id, 'Org', 'Club', :email, 'x', now(), now(), true, 0, false)"
                ),
                {"id": str(organizador.value), "email": f"org_{uuid4()}@test.com"},
            )
            competiciones = SQLAlchemyCompetitionRepository(sesion)
            inscripciones = SQLAlchemyEnrollmentRepository(sesion)
            for _ in range(MAX_ENROLLMENTS_PER_USER):
                otra = _competicion_publica(organizador)
                await competiciones.add(otra)
                await inscripciones.add(
                    Enrollment.direct_enroll(
                        id=EnrollmentId.generate(), competition_id=otra.id, user_id=quien
                    )
                )
            await sesion.commit()
    finally:
        await engine.dispose()
    competicion_id, _ = await _publica(client, date.today() + timedelta(days=5))

    respuesta = await _pide(client, competicion_id, cookies)

    assert respuesta.status_code == 400, respuesta.text
    assert "máximo" in respuesta.json()["detail"]


def _competicion_publica(organizador: UserId) -> Competition:
    empieza = date.today() + timedelta(days=5)
    return Competition(
        id=CompetitionId.generate(),
        creator_id=organizador,
        name=CompetitionName(f"Club {uuid4().hex[:6]}"),
        dates=DateRange(empieza, empieza + timedelta(days=1)),
        location=Location(CountryCode("ES")),
        team_1_name="Europa",
        team_2_name="América",
        play_mode=PlayMode.SCRATCH,
        status=CompetitionStatus.ACTIVE,
        visibility=Visibility.PUBLIC,
    )


async def test_aprobar_con_la_competicion_llena_es_un_400_con_el_motivo(client: AsyncClient):
    """El gemelo del organizador: el día del torneo puede haber más solicitudes
    pendientes que plazas, y aprobar la que sobra reventaba igual."""
    competicion_id, organiza = await _publica(
        client, date.today() + timedelta(days=5), max_players=2
    )
    primera = await _pide(client, competicion_id, await _jugador(client, "primera"))
    segunda = await _pide(client, competicion_id, await _jugador(client, "segunda"))
    assert primera.status_code == segunda.status_code == 201
    aprobada = await client.post(
        f"/api/v1/enrollments/{primera.json()['id']}/approve", cookies=organiza
    )
    assert aprobada.status_code == 200, aprobada.text

    respuesta = await client.post(
        f"/api/v1/enrollments/{segunda.json()['id']}/approve", cookies=organiza
    )

    assert respuesta.status_code == 400, respuesta.text
    assert "completa" in respuesta.json()["detail"]
