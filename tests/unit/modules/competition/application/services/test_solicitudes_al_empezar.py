"""
Al empezar la competición, las solicitudes pendientes se rechazan (decidido el
21 oct). Cerrar la inscripción no las toca: en una Ryder el organizador puede
aprobarlas con la inscripción ya cerrada.

LA TABLA:

    #    situacion                                       | debe
    -----|-----------------------------------------------|---------------------------
    S1'  se cierra a mano                                | siguen REQUESTED
    S1'  se cierra al nombrar capitanes                  | siguen REQUESTED
    S1'  Ryder cerrada: el organizador aprueba           | APPROVED
    S1'  empieza a mano (START)                          | REQUESTED -> REJECTED
    S1'  empieza con el primer golpe de una partida      | REQUESTED -> REJECTED
    S1'  empieza con el primer golpe de un partido       | REQUESTED -> REJECTED
    S1'  empieza con un hoyo que corrige el organizador  | REQUESTED -> REJECTED
    S1'  un golpe con la competición ya en juego         | no toca nada
    S1'  el organizador las contaba como pendientes      | al empezar, ninguna
    S2   sin aviso                                       | ningún evento nuevo
    S2   APPROVED/INVITED/WITHDRAWN/CANCELLED/REJECTED   | intactas
    S2   las de otra competición                         | intactas
    S2   dos veces                                       | igual que una
"""

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CloseEnrollmentsRequestDTO,
    NameCaptainsRequestDTO,
    StartCompetitionRequestDTO,
)
from src.modules.competition.application.dto.enrollment_dto import HandleEnrollmentRequestDTO
from src.modules.competition.application.dto.partidas_dto import CorrectHoleBodyDTO
from src.modules.competition.application.services.solicitudes_al_empezar import (
    rechazar_las_solicitudes_pendientes,
)
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    arrancar_la_competicion,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.name_captains_use_case import (
    NameCaptainsUseCase,
)
from src.modules.competition.application.use_cases.organizador_de_partidas_use_case import (
    CorregirHoyoDePartidaUseCase,
)
from src.modules.competition.application.use_cases.start_competition_use_case import (
    StartCompetitionUseCase,
)
from src.modules.competition.application.use_cases.submit_hole_score_use_case import (
    SubmitHoleScoreUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.events.enrollment_requested_event import (
    EnrollmentRequestedEvent,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.competition.application.use_cases.helpers import (
    USUARIOS_CON_GENERO,
    create_approved_enrollment,
    create_competition,
)
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    _partida,
)

pytestmark = pytest.mark.asyncio


async def _abierta() -> tuple[InMemoryUnitOfWork, CompetitionId, UserId]:
    """Una Ryder con la inscripción abierta."""
    uow = InMemoryUnitOfWork()
    creator_id = UserId(uuid4())
    creada = await create_competition(uow, creator_id)
    return uow, CompetitionId(creada.id), creator_id


async def _solicitud(uow, competition_id: CompetitionId) -> Enrollment:
    """Una solicitud pendiente de un jugador cualquiera."""
    solicitud = Enrollment.request(
        id=EnrollmentId.generate(), competition_id=competition_id, user_id=UserId(uuid4())
    )
    async with uow:
        await uow.enrollments.add(solicitud)
    return solicitud


async def _estado(uow, enrollment: Enrollment) -> EnrollmentStatus:
    async with uow:
        return (await uow.enrollments.find_by_id(enrollment.id)).status


async def _cerrar_a_mano(uow, competition_id: CompetitionId, creator_id: UserId) -> None:
    await CloseEnrollmentsUseCase(uow).execute(
        CloseEnrollmentsRequestDTO(competition_id=competition_id.value), creator_id
    )


async def _cerrada_con_una_solicitud(
    uow, competition_id: CompetitionId, creator_id: UserId
) -> Enrollment:
    """Cerrada a mano con una solicitud sin atender, y con una sesión para poder empezar."""
    solicitud = await _solicitud(uow, competition_id)
    await _cerrar_a_mano(uow, competition_id, creator_id)
    async with uow:
        await uow.rounds.add(
            Round.create(
                competition_id=competition_id,
                golf_course_id=GolfCourseId(uuid4()),
                round_date=date(2026, 6, 1),
                session_type=SessionType.MORNING,
                match_format=MatchFormat.SINGLES,
            )
        )
    return solicitud


async def _iniciar_a_mano(uow, competition_id: CompetitionId, creator_id: UserId) -> None:
    await StartCompetitionUseCase(uow).execute(
        StartCompetitionRequestDTO(competition_id=competition_id.value), creator_id
    )


# --- S1': cerrar no las toca ---------------------------------------------------


async def test_cerrar_a_mano_no_rechaza_las_solicitudes_pendientes():
    uow, comp_id, creator_id = await _abierta()
    solicitudes = [await _solicitud(uow, comp_id) for _ in range(2)]

    await _cerrar_a_mano(uow, comp_id, creator_id)

    assert [await _estado(uow, s) for s in solicitudes] == [EnrollmentStatus.REQUESTED] * 2


async def test_nombrar_capitanes_no_rechaza_las_solicitudes_pendientes():
    uow, comp_id, creator_id = await _abierta()
    ana, bea = UserId(uuid4()), UserId(uuid4())
    for jugador in (ana, bea):
        await create_approved_enrollment(uow, comp_id.value, jugador)
    solicitud = await _solicitud(uow, comp_id)

    await NameCaptainsUseCase(uow).execute(
        NameCaptainsRequestDTO(
            competition_id=comp_id.value, team_a_captain_id=ana.value, team_b_captain_id=bea.value
        ),
        creator_id,
    )

    async with uow:
        assert (await uow.competitions.find_by_id(comp_id)).status == CompetitionStatus.CLOSED
    assert await _estado(uow, solicitud) == EnrollmentStatus.REQUESTED


async def test_en_una_ryder_cerrada_el_organizador_aun_la_aprueba():
    uow, comp_id, creator_id = await _abierta()
    solicitud = await _solicitud(uow, comp_id)
    await _cerrar_a_mano(uow, comp_id, creator_id)

    respuesta = await HandleEnrollmentUseCase(uow, USUARIOS_CON_GENERO).execute(
        HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="APPROVE"),
        creator_id,
    )

    assert respuesta.status == "APPROVED"


# --- S1': empezar las rechaza, por los cuatro caminos ----------------------------


async def test_iniciar_a_mano_rechaza_las_solicitudes_pendientes():
    uow, comp_id, creator_id = await _abierta()
    solicitud = await _cerrada_con_una_solicitud(uow, comp_id, creator_id)

    await _iniciar_a_mano(uow, comp_id, creator_id)

    assert await _estado(uow, solicitud) == EnrollmentStatus.REJECTED


async def test_el_primer_golpe_de_una_partida_rechaza_las_solicitudes_pendientes():
    uow, comp_id, creator_id = await _abierta()
    solicitud = await _cerrada_con_una_solicitud(uow, comp_id, creator_id)

    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        await arrancar_la_competicion(uow, competicion)

    assert await _estado(uow, solicitud) == EnrollmentStatus.REJECTED


async def test_el_primer_golpe_de_un_partido_rechaza_las_solicitudes_pendientes():
    uow, comp_id, creator_id = await _abierta()
    solicitud = await _cerrada_con_una_solicitud(uow, comp_id, creator_id)
    caso = SubmitHoleScoreUseCase(uow, MagicMock(), MagicMock())

    async with uow:
        await caso._arranca_la_competicion(comp_id, RuntimeError("no se puede"))

    assert await _estado(uow, solicitud) == EnrollmentStatus.REJECTED


async def test_el_organizador_corrigiendo_un_hoyo_rechaza_las_solicitudes_pendientes():
    escenario, partida = await _partida()
    comp_id = escenario.competicion.id
    assert escenario.competicion.status == CompetitionStatus.CLOSED
    solicitud = await _solicitud(escenario.uow, comp_id)

    await CorregirHoyoDePartidaUseCase(
        uow=escenario.uow, zonas=escenario.zonas, reloj=lambda: escenario.ahora
    ).execute(
        partida.id.value,
        partida.user_ids[0].value,
        1,
        CorrectHoleBodyDTO(own_score=4),
        escenario.creador,
        False,
    )

    assert (await escenario.uow.competitions.find_by_id(comp_id)).status == (
        CompetitionStatus.IN_PROGRESS
    )
    assert await _estado(escenario.uow, solicitud) == EnrollmentStatus.REJECTED


async def test_un_golpe_con_la_competicion_ya_en_juego_no_toca_nada():
    """Ya en juego no arranca: no es momento de rechazar a nadie."""
    uow, comp_id, creator_id = await _abierta()
    solicitud = await _cerrada_con_una_solicitud(uow, comp_id, creator_id)
    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        competicion.start()
        await uow.competitions.update(competicion)
    caso = SubmitHoleScoreUseCase(uow, MagicMock(), MagicMock())

    async with uow:
        await caso._arranca_la_competicion(comp_id, RuntimeError("no se puede"))
        await arrancar_la_competicion(uow, await uow.competitions.find_by_id(comp_id))

    assert await _estado(uow, solicitud) == EnrollmentStatus.REQUESTED


async def test_el_organizador_las_ve_pendientes_hasta_que_empieza():
    uow, comp_id, creator_id = await _abierta()
    for _ in range(2):
        await _solicitud(uow, comp_id)
    await _cerrada_con_una_solicitud(uow, comp_id, creator_id)
    async with uow:
        assert await uow.enrollments.count_pending(comp_id) == 3

    await _iniciar_a_mano(uow, comp_id, creator_id)

    async with uow:
        assert await uow.enrollments.count_pending(comp_id) == 0


# --- S2 ---------------------------------------------------------------------


async def test_se_rechazan_sin_aviso():
    """Sin correo ni notificación: ningún evento más que el de haberla pedido."""
    uow, comp_id, creator_id = await _abierta()
    solicitud = await _cerrada_con_una_solicitud(uow, comp_id, creator_id)

    await _iniciar_a_mano(uow, comp_id, creator_id)

    async with uow:
        guardada = await uow.enrollments.find_by_id(solicitud.id)
    assert guardada.status == EnrollmentStatus.REJECTED
    assert [type(e) for e in guardada.get_domain_events()] == [EnrollmentRequestedEvent]


async def test_solo_toca_las_solicitudes_pendientes_de_esa_competicion():
    uow, comp_id, _ = await _abierta()
    otra = CompetitionId((await create_competition(uow, UserId(uuid4()))).id)
    solicitud = await _solicitud(uow, comp_id)
    de_otra = await _solicitud(uow, otra)

    def _en(status_cambio):
        enrollment = Enrollment.request(
            id=EnrollmentId.generate(), competition_id=comp_id, user_id=UserId(uuid4())
        )
        status_cambio(enrollment)
        return enrollment

    resto = {
        EnrollmentStatus.APPROVED: _en(lambda e: e.approve()),
        EnrollmentStatus.REJECTED: _en(lambda e: e.reject()),
        EnrollmentStatus.CANCELLED: _en(lambda e: e.cancel()),
        EnrollmentStatus.WITHDRAWN: _en(lambda e: (e.approve(), e.withdraw())),
        EnrollmentStatus.INVITED: Enrollment.invite(
            id=EnrollmentId.generate(), competition_id=comp_id, user_id=UserId(uuid4())
        ),
    }
    async with uow:
        for enrollment in resto.values():
            await uow.enrollments.add(enrollment)

    async with uow:
        await rechazar_las_solicitudes_pendientes(uow, comp_id)

    assert await _estado(uow, solicitud) == EnrollmentStatus.REJECTED
    assert await _estado(uow, de_otra) == EnrollmentStatus.REQUESTED
    assert {s: await _estado(uow, e) for s, e in resto.items()} == {s: s for s in resto}


async def test_dos_veces_es_igual_que_una():
    uow, comp_id, _ = await _abierta()
    solicitud = await _solicitud(uow, comp_id)

    async with uow:
        await rechazar_las_solicitudes_pendientes(uow, comp_id)
        await rechazar_las_solicitudes_pendientes(uow, comp_id)

    assert await _estado(uow, solicitud) == EnrollmentStatus.REJECTED
