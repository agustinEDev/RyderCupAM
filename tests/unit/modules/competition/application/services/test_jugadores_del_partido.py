"""
Los jugadores de un partido con el reparto de golpes de su formato (BE #502).

Estaba dentro de la reasignación, y salió a su propio sitio para compartirlo.
Trae a los usuarios en una sola consulta: la
reasignación los pedía todos a la vez sobre la misma sesión, y SQLAlchemy no
admite dos consultas a la vez en una sesión.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.services.jugadores_del_partido import (
    JugadoresDelPartido,
    PlayerNotEnrolledError,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio

TORNEO = CompetitionId.generate()


def _usuario(user_id: UserId, handicap: float):
    usuario = MagicMock()
    usuario.id = user_id
    usuario.handicap = MagicMock(value=handicap)
    usuario.gender = Gender.MALE
    return usuario


async def _inscrito(uow, user_id: UserId) -> None:
    async with uow:
        await uow.enrollments.add(
            Enrollment.direct_enroll(
                id=EnrollmentId.generate(),
                competition_id=TORNEO,
                user_id=user_id,
                tee_color=TeeColor.YELLOW,
            )
        )


def _sesion() -> Round:
    return Round.create(
        competition_id=TORNEO,
        golf_course_id=GolfCourseId(uuid4()),
        round_date=date(2030, 10, 12),
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )


def _scratch():
    competicion = MagicMock()
    competicion.id = TORNEO
    competicion.play_mode = PlayMode.SCRATCH
    competicion.max_playing_handicap = None
    return competicion


async def test_una_sola_consulta_de_usuarios():
    uow = InMemoryUnitOfWork()
    a, b = UserId.generate(), UserId.generate()
    for u in (a, b):
        await _inscrito(uow, u)
    usuarios = MagicMock()
    usuarios.find_by_ids = AsyncMock(return_value=[_usuario(a, 10.0), _usuario(b, 4.0)])
    usuarios.find_by_id = AsyncMock()
    campo = _campo_con_amarillas()

    lado_a, lado_b = await JugadoresDelPartido(campo, usuarios).construir(
        uow, _sesion(), _con_handicap(), [a], [b]
    )

    usuarios.find_by_ids.assert_awaited_once()
    usuarios.find_by_id.assert_not_awaited()
    assert [p.user_id for p in lado_a] == [a]
    assert [p.user_id for p in lado_b] == [b]


async def test_quien_no_esta_inscrito_no_puede_jugar():
    uow = InMemoryUnitOfWork()
    inscrito, intruso = UserId.generate(), UserId.generate()
    await _inscrito(uow, inscrito)

    with pytest.raises(PlayerNotEnrolledError):
        await JugadoresDelPartido(MagicMock(), MagicMock()).construir(
            uow, _sesion(), _scratch(), [inscrito], [intruso]
        )


async def test_en_scratch_sin_campo_juegan_igual_sin_genero():
    uow = InMemoryUnitOfWork()
    a, b = UserId.generate(), UserId.generate()
    for u in (a, b):
        await _inscrito(uow, u)
    campo, usuarios = MagicMock(), MagicMock()
    campo.find_by_id = AsyncMock(return_value=None)
    usuarios.find_by_ids = AsyncMock(return_value=[_usuario(a, 10.0), _usuario(b, 4.0)])

    lado_a, _ = await JugadoresDelPartido(campo, usuarios).construir(
        uow, _sesion(), _scratch(), [a], [b]
    )

    assert len(lado_a[0].strokes_received) == 0
    assert lado_a[0].tee_gender is None


async def test_en_scratch_cada_uno_guarda_el_genero_de_su_barra():
    """
    GIVEN: Una Ryder SCRATCH en un campo con amarillas de hombre
    WHEN: Se construyen los jugadores de un partido (reasignación)
    THEN: Juegan sin golpes y con su barra con género (RyderCupWeb #880)
    """
    uow = InMemoryUnitOfWork()
    a, b = UserId.generate(), UserId.generate()
    for u in (a, b):
        await _inscrito(uow, u)
    usuarios = MagicMock()
    usuarios.find_by_ids = AsyncMock(return_value=[_usuario(a, 10.0), _usuario(b, 4.0)])

    lado_a, lado_b = await JugadoresDelPartido(_campo_con_amarillas(), usuarios).construir(
        uow, _sesion(), _scratch(), [a], [b]
    )

    for jugador in (*lado_a, *lado_b):
        assert (jugador.tee_color, jugador.tee_gender) == (TeeColor.YELLOW, Gender.MALE)
        assert jugador.playing_handicap == 0
        assert len(jugador.strokes_received) == 0
        # Del perfil solo se lee el género: el hándicap no cuenta en SCRATCH
        assert jugador.player_handicap == Decimal("0")


def _con_handicap():
    competicion = _scratch()
    competicion.play_mode = PlayMode.HANDICAP
    return competicion


def _campo_con_amarillas():
    """El mismo campo de mentira que usan los tests de la generación de partidos."""
    tee = MagicMock()
    tee.color = TeeColor.YELLOW
    tee.gender = Gender.MALE
    tee.course_rating = Decimal("71.2")
    tee.slope_rating = 128
    hoyos = []
    for numero in range(1, 19):
        hoyo = MagicMock()
        hoyo.number = numero
        hoyo.par = 4
        hoyo.stroke_index = numero
        hoyos.append(hoyo)
    campo = MagicMock()
    campo.tees = [tee]
    campo.reference_card = hoyos
    repo = MagicMock()
    repo.find_by_id = AsyncMock(return_value=campo)
    return repo
