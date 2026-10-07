"""
Una actualización de hándicaps lanzada en segundo plano, contra Postgres (#251).

Con sus piezas de verdad: la tarea del proceso, una sesión por parte de la
pasada, el registro y la corrección del hándicap fijado. Solo la RFEG y el
correo son de mentira.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.refresco_de_handicaps import LanzadorEnSegundoPlano
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    EstadoActualizacion,
    OrigenActualizacion,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.enrollment_repository import (
    SQLAlchemyEnrollmentRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.handicap_update_repository import (
    SQLAlchemyHandicapUpdateRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    enrollments_table,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _jugador(sesion: AsyncSession, handicap: float) -> User:
    usuario = User.create(
        first_name="Jugador",
        last_name=uuid4().hex[:8],
        email_str=f"vig-{uuid4().hex[:8]}@test.com",
        plain_password="P@ssw0rd123!",
        country_code_str="ES",
        gender=Gender.MALE,
    )
    usuario.update_handicap(handicap)
    await SQLAlchemyUserRepository(sesion).save(usuario)
    await sesion.commit()
    return usuario


async def _medal_cerrado(sesion: AsyncSession, jugadores: list[User]) -> CompetitionId:
    competicion = Competition(
        id=CompetitionId.generate(),
        creator_id=jugadores[0].id,
        name=CompetitionName(f"Medal {uuid4().hex[:6]}"),
        dates=DateRange(date(2030, 10, 12), date(2030, 10, 12)),
        location=Location(CountryCode("ES")),
        play_mode=PlayMode.HANDICAP,
        tournament_type=TournamentType.MEDAL,
        status=CompetitionStatus.CLOSED,
    )
    await SQLAlchemyCompetitionRepository(sesion).add(competicion)
    for usuario in jugadores:
        inscripcion = Enrollment.direct_enroll(
            id=EnrollmentId.generate(), competition_id=competicion.id, user_id=usuario.id
        )
        inscripcion.congelar_handicap(Decimal(str(usuario.handicap.value)), 1)
        await SQLAlchemyEnrollmentRepository(sesion).add(inscripcion)
    await sesion.commit()
    return competicion.id


async def _actualizacion(sesion: AsyncSession, torneo: CompetitionId) -> ActualizacionDeHandicaps:
    actualizacion = ActualizacionDeHandicaps.crear(
        torneo, OrigenActualizacion.CIERRE, datetime.now(UTC)
    )
    await SQLAlchemyHandicapUpdateRepository(sesion).add(actualizacion)
    await sesion.commit()
    return actualizacion


def _rfeg(handicap: float | None) -> MagicMock:
    rfeg = MagicMock()
    rfeg.search_handicap = AsyncMock(return_value=handicap)
    return rfeg


def _avisos() -> MagicMock:
    avisos = MagicMock()
    avisos.send_handicaps_pending_email = AsyncMock(return_value=True)
    return avisos


async def _sin_pausas(_segundos: float) -> None:
    return None


async def test_lanzada_en_segundo_plano_corrige_el_fijado_y_queda_completa(db_session):
    jugador = await _jugador(db_session, 8.0)
    torneo = await _medal_cerrado(db_session, [jugador])
    actualizacion = await _actualizacion(db_session, torneo)
    fabrica = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    avisos = _avisos()
    lanzador = LanzadorEnSegundoPlano(fabrica, _rfeg(13.0), avisos, esperar=_sin_pausas)

    lanzador.lanzar(actualizacion.id)
    await lanzador.esperar_a_todas()

    async with fabrica() as otra:
        fijado = await otra.scalar(
            select(enrollments_table.c.fixed_handicap).where(
                enrollments_table.c.competition_id == torneo
            )
        )
        repo = SQLAlchemyHandicapUpdateRepository(otra)
        terminada = await repo.find_by_id(actualizacion.id)
        resultados = await repo.resultados(actualizacion.id)
    assert fijado == Decimal("13.0")
    assert terminada.estado is EstadoActualizacion.COMPLETA
    assert [(r.resultado.value, r.intentos) for r in resultados.values()] == [("ACTUALIZADO", 1)]
    avisos.send_handicaps_pending_email.assert_not_awaited()


async def test_si_la_rfeg_no_contesta_queda_incompleta_y_avisa(db_session):
    jugador = await _jugador(db_session, 8.0)
    torneo = await _medal_cerrado(db_session, [jugador])
    actualizacion = await _actualizacion(db_session, torneo)
    fabrica = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    rfeg = _rfeg(None)
    rfeg.search_handicap.side_effect = TimeoutError
    avisos = _avisos()

    await LanzadorEnSegundoPlano(fabrica, rfeg, avisos, esperar=_sin_pausas).pasada(
        actualizacion.id
    )

    async with fabrica() as otra:
        terminada = await SQLAlchemyHandicapUpdateRepository(otra).find_by_id(actualizacion.id)
    assert terminada.estado is EstadoActualizacion.INCOMPLETA
    assert rfeg.search_handicap.await_count == 3
    avisos.send_handicaps_pending_email.assert_awaited_once()
    assert avisos.send_handicaps_pending_email.await_args.kwargs["to_email"] == str(jugador.email)
