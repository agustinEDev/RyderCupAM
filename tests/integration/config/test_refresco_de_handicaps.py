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
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.dependencies import actividad_en_sesion_propia
from src.config.refresco_de_handicaps import (
    CANDADO_DEL_VIGILANTE,
    LanzadorEnSegundoPlano,
    VigilanteDeActualizaciones,
)
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    EstadoActualizacion,
    OrigenActualizacion,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    CorreoDeActualizacion,
)
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
from src.modules.social.infrastructure.persistence.mappers.activity_event_mapper import (
    activity_events_table,
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
    avisos.send_handicap_not_found_email = AsyncMock(return_value=True)
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


async def test_el_vigilante_lanza_la_programada_que_llega_a_su_hora(db_session):
    jugador = await _jugador(db_session, 8.0)
    torneo = await _medal_cerrado(db_session, [jugador])
    ahora = datetime.now(UTC)
    await SQLAlchemyHandicapUpdateRepository(db_session).programar(torneo, ahora, ahora)
    await db_session.commit()
    fabrica = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    lanzador = LanzadorEnSegundoPlano(fabrica, _rfeg(13.0), _avisos(), esperar=_sin_pausas)

    atendidas = await VigilanteDeActualizaciones(lanzador).vuelta()
    await lanzador.esperar_a_todas()

    async with fabrica() as otra:
        repo = SQLAlchemyHandicapUpdateRepository(otra)
        ultima = await repo.ultima_de(torneo)
        programada = await repo.programada_de(torneo)
    assert atendidas == 1
    assert programada is None
    assert ultima.origen is OrigenActualizacion.PROGRAMADA
    assert ultima.estado is EstadoActualizacion.COMPLETA


async def test_con_el_candado_cogido_el_vigilante_se_salta_la_vuelta(db_session):
    fabrica = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    lanzador = LanzadorEnSegundoPlano(fabrica, _rfeg(13.0), _avisos(), esperar=_sin_pausas)

    async with db_session.bind.connect() as otro_proceso:
        await otro_proceso.scalar(text("SELECT pg_advisory_lock(:k)"), {"k": CANDADO_DEL_VIGILANTE})
        resultado = await VigilanteDeActualizaciones(lanzador).vuelta()
        await otro_proceso.scalar(
            text("SELECT pg_advisory_unlock(:k)"), {"k": CANDADO_DEL_VIGILANTE}
        )

    assert resultado is None


async def test_un_espanol_no_encontrado_avisa_en_actividad_y_por_correo(db_session):
    """
    Given un Medal cerrado en España con un español al que la RFEG no encuentra
    When se lanza la pasada con Actividad de verdad (15 nov 2026, H2 y H3)
    Then el organizador tiene su aviso con 1, el jugador el suyo y su correo,
         y queda apuntado que ya se le escribió (D2)
    """
    organizador = await _jugador(db_session, 8.0)
    perdido = await _jugador(db_session, 20.0)
    torneo = await _medal_cerrado(db_session, [organizador, perdido])
    actualizacion = await _actualizacion(db_session, torneo)
    fabrica = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    rfeg = MagicMock()
    rfeg.search_handicap = AsyncMock(
        side_effect=lambda nombre: None if nombre == perdido.get_full_name() else 9.0
    )
    avisos = _avisos()

    await LanzadorEnSegundoPlano(
        fabrica, rfeg, avisos, esperar=_sin_pausas, actividad=actividad_en_sesion_propia
    ).pasada(actualizacion.id)

    async with fabrica() as otra:
        filas = (
            await otra.execute(
                select(
                    activity_events_table.c.user_id,
                    activity_events_table.c.type,
                    activity_events_table.c.payload,
                ).where(activity_events_table.c.source_match_id == str(torneo.value))
            )
        ).all()
        repo = SQLAlchemyHandicapUpdateRepository(otra)
        terminada = await repo.find_by_id(actualizacion.id)
        resultados = await repo.resultados(actualizacion.id)
    assert terminada.estado is EstadoActualizacion.COMPLETA
    assert sorted(r.resultado.value for r in resultados.values()) == [
        "ACTUALIZADO",
        "NO_ENCONTRADO",
    ]
    async with fabrica() as otra:
        repo = SQLAlchemyHandicapUpdateRepository(otra)
        escrito = await repo.correo_enviado(torneo, perdido.id, CorreoDeActualizacion.NO_ENCONTRADO)
        lista = await repo.correo_enviado(
            torneo, organizador.id, CorreoDeActualizacion.LISTA_DEL_ORGANIZADOR
        )
    assert escrito == ""
    assert lista is not None and len(lista) == 64
    # El tipo de la columna puede devolver el UserId o el UUID: se compara el UUID
    avisados = {
        (str(getattr(f.user_id, "value", f.user_id)), str(f.type)): f.payload for f in filas
    }
    assert set(avisados) == {
        (str(organizador.id.value), "HANDICAPS_NOT_UPDATED"),
        (str(perdido.id.value), "RFEG_HANDICAP_NOT_FOUND"),
    }
    assert avisados[(str(organizador.id.value), "HANDICAPS_NOT_UPDATED")]["count"] == 1
    avisos.send_handicap_not_found_email.assert_awaited_once()
    assert avisos.send_handicap_not_found_email.await_args.kwargs["to_email"] == str(perdido.email)
