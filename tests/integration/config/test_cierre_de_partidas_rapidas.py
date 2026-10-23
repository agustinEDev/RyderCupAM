"""
El cierre de las partidas rápidas que nadie termina, contra Postgres de verdad
(Agustín, 23 oct 2026): la columna `started_at`, el listado de las abiertas, el
cierre con su sesión propia y el candado entre procesos.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.cierre_de_partidas_rapidas import CANDADO_DEL_CIERRE, CierreDePartidasRapidas
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.repositories.golf_course_repository import (
    GolfCourseRepository,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.quick_match.infrastructure.persistence.sqlalchemy.quick_match_hole_score_repository import (
    SQLAlchemyQuickMatchHoleScoreRepository,
)
from src.modules.quick_match.infrastructure.persistence.sqlalchemy.quick_match_repository import (
    SQLAlchemyQuickMatchRepository,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

AHORA = datetime.now(UTC).replace(tzinfo=None)
HACE_TRES_DIAS = AHORA - timedelta(days=3)
# El reloj de la vuelta: ya vencidas las de hace tres días, y todavía no las que
# otros tests crean ahora en la misma base, que no se tocan
RELOJ = AHORA - timedelta(hours=12)


async def _usuario(sesion: AsyncSession) -> User:
    usuario = User.create(
        first_name="Cierre",
        last_name=uuid4().hex[:8],
        email_str=f"cierre-{uuid4().hex[:8]}@test.com",
        plain_password="P@ssw0rd123!",
        country_code_str="ES",
        gender=Gender.MALE,
    )
    await SQLAlchemyUserRepository(sesion).save(usuario)
    await sesion.flush()
    return usuario


async def _campo(sesion: AsyncSession, creador: User) -> GolfCourse:
    campo = GolfCourse.create(
        name=f"Cierre {uuid4().hex[:6]}",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creador.id,
        tees=[
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier="Yellow",
                course_rating=70.0,
                slope_rating=125,
            )
        ],
        holes=[Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)],
        timezone="Europe/Madrid",
    )
    campo.approve()
    await GolfCourseRepository(sesion).save(campo)
    await sesion.flush()
    return campo


async def _partida(sesion: AsyncSession, *, con_golpe: bool) -> QuickMatch:
    creador = await _usuario(sesion)
    rival = await _usuario(sesion)
    campo = await _campo(sesion, creador)
    partida = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creador.id,
        golf_course_id=campo.id,
        match_format=MatchFormat.SINGLES,
    )
    partida.add_participant(QuickMatchParticipant.for_user(rival.id))
    partida.start([partida.creator_participant_id])
    partida._created_at = partida._started_at = HACE_TRES_DIAS
    await SQLAlchemyQuickMatchRepository(sesion).add(partida)
    await sesion.flush()
    if con_golpe:
        await SQLAlchemyQuickMatchHoleScoreRepository(sesion).add(
            QuickMatchHoleScore(
                id=QuickMatchHoleScoreId.generate(),
                quick_match_id=partida.id,
                hole_number=1,
                participant_id=partida.creator_participant_id,
                score=None,
                recorded_by_participant_id=partida.creator_participant_id,
            )
        )
    await sesion.commit()
    return partida


async def _estado(fabrica, partida: QuickMatch) -> tuple:
    async with fabrica() as sesion:
        fila = (
            await sesion.execute(
                text("SELECT status, started_at FROM quick_matches WHERE id = :id"),
                {"id": partida.id.value},
            )
        ).one()
    return fila.status, fila.started_at


async def test_it_keeps_when_it_started_and_lists_the_open_ones(db_session):
    fabrica = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    async with fabrica() as sesion:
        partida = await _partida(sesion, con_golpe=False)
        terminada = await _partida(sesion, con_golpe=True)
        terminada.complete()
        await SQLAlchemyQuickMatchRepository(sesion).update(terminada)
        await sesion.commit()

    async with fabrica() as sesion:
        abiertas = await SQLAlchemyQuickMatchRepository(sesion).list_open()

    assert partida.id in {p.id for p in abiertas}
    assert terminada.id not in {p.id for p in abiertas}
    assert next(p for p in abiertas if p.id == partida.id).started_at == HACE_TRES_DIAS


async def test_a_pass_closes_the_expired_ones(db_session):
    fabrica = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    async with fabrica() as sesion:
        con_raya = await _partida(sesion, con_golpe=True)
        vacia = await _partida(sesion, con_golpe=False)

    resumen = await CierreDePartidasRapidas(fabrica, reloj=lambda: RELOJ).vuelta()

    assert resumen is not None
    assert (await _estado(fabrica, con_raya))[0] == QuickMatchStatus.COMPLETED.value
    assert (await _estado(fabrica, vacia))[0] == QuickMatchStatus.CANCELLED.value


async def test_with_the_lock_taken_the_pass_is_skipped(db_session):
    fabrica = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    async with fabrica() as sesion:
        partida = await _partida(sesion, con_golpe=True)

    async with db_session.bind.connect() as otro_proceso:
        await otro_proceso.scalar(text("SELECT pg_advisory_lock(:k)"), {"k": CANDADO_DEL_CIERRE})
        resultado = await CierreDePartidasRapidas(fabrica, reloj=lambda: RELOJ).vuelta()
        await otro_proceso.scalar(text("SELECT pg_advisory_unlock(:k)"), {"k": CANDADO_DEL_CIERRE})

    assert resultado is None
    assert (await _estado(fabrica, partida))[0] == QuickMatchStatus.IN_PROGRESS.value


async def test_a_match_that_fails_to_close_does_not_stop_the_others(db_session, monkeypatch):
    """
    Hallazgo 1 del revisor: el rollback de la que falla caduca lo cargado en la
    sesión, y leerlo después reventaba la vuelta entera. Las demás se cierran.
    """
    fabrica = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    async with fabrica() as sesion:
        rota = await _partida(sesion, con_golpe=True)
        buena = await _partida(sesion, con_golpe=True)
        # La rota, la primera de la vuelta (van de la más antigua a la más nueva)
        await sesion.execute(
            text("UPDATE quick_matches SET created_at = :c, started_at = :c WHERE id = :id"),
            {"c": HACE_TRES_DIAS - timedelta(hours=1), "id": rota.id.value},
        )
        await sesion.commit()

    guardar = SQLAlchemyQuickMatchRepository.update

    async def falla_con_la_rota(self, partida):
        if partida.id == rota.id:
            await self._session.execute(text("SELECT 1/0"))
        return await guardar(self, partida)

    monkeypatch.setattr(SQLAlchemyQuickMatchRepository, "update", falla_con_la_rota)

    resumen = await CierreDePartidasRapidas(fabrica, reloj=lambda: RELOJ).vuelta()

    assert resumen is not None
    assert (await _estado(fabrica, rota))[0] == QuickMatchStatus.IN_PROGRESS.value
    assert (await _estado(fabrica, buena))[0] == QuickMatchStatus.COMPLETED.value
