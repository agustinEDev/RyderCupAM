"""
El organizador quita a un inscrito (release social 2, tabla del 27 oct 2026).

| #   | Caso                                                    | Resultado                              |
|-----|---------------------------------------------------------|----------------------------------------|
| Q1  | El organizador (o un admin) quita a un aprobado         | WITHDRAWN                              |
| Q1  | Otro jugador                                            | No puede (403)                         |
| Q2  | Lo mismo que retirarse: sale de sus partidas, franjas…  | El servicio compartido (ver retirada)  |
| Q3  | En juego, terminada o cancelada                         | No se deja                             |
| Q4  | Ryder con partidos generados en los que juega           | No se deja                             |
| Q4  | Con equipos formados y sin partidos                     | Sale y los equipos se deshacen         |
| Q5  | A sí mismo (el organizador)                             | No se deja                             |
| -   | Una solicitud o una invitación (no aprobada)            | No se quita (es rechazar)              |
| N1  | Se le avisa                                             | Primero `left`, luego `removed`        |
| W   | Un jugador de un equipo formado se retira él mismo      | También se deshacen (decidido 27 oct)  |
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    RemoveEnrolledPlayerRequestDTO,
    WithdrawEnrollmentRequestDTO,
)
from src.modules.competition.application.exceptions import (
    EnrollmentNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.services.esperas_de_la_competicion import (
    EsperasDeLaCompeticion,
)
from src.modules.competition.application.use_cases.remove_enrolled_player_use_case import (
    CannotRemoveOrganizerError,
    DraftInProgressError,
    PlayerHasMatchesError,
    RemovalNotAllowedError,
    RemoveEnrolledPlayerUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.entities.draft import Draft
from src.modules.competition.domain.entities.enrollment import Enrollment, EnrollmentStateError
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.draft_id import DraftId
from src.modules.competition.domain.value_objects.draft_status import DraftStatus
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
    set_competition_status,
)
from tests.unit.modules.competition.application.use_cases.test_avisos_de_actividad import (
    _Registro,
)
from tests.unit.modules.competition.application.use_cases.test_deshacer_equipos import (
    _jugador,
    _montar,
)

pytestmark = pytest.mark.asyncio


async def _abierta():
    uow = InMemoryUnitOfWork()
    organizador = UserId(uuid4())
    creada = await create_competition(uow, organizador)
    jugador = UserId(uuid4())
    inscripcion = await create_approved_enrollment(uow, creada.id, jugador)
    return uow, organizador, CompetitionId(creada.id), jugador, inscripcion


def _pide(enrollment_id) -> RemoveEnrolledPlayerRequestDTO:
    return RemoveEnrolledPlayerRequestDTO(enrollment_id=enrollment_id.value)


def _quita(uow, registro=None):
    return RemoveEnrolledPlayerUseCase(uow, actividad=registro)


async def _suya(uow, inscripcion) -> Enrollment:
    async with uow:
        return await uow.enrollments.find_by_id(inscripcion.id)


async def test_q1_el_organizador_le_quita_y_se_le_avisa_tras_salir():
    uow, organizador, comp_id, jugador, inscripcion = await _abierta()
    registro = _Registro()

    respuesta = await _quita(uow, registro).execute(_pide(inscripcion.id), organizador)

    assert respuesta.status == "WITHDRAWN"
    assert (await _suya(uow, inscripcion)).status == EnrollmentStatus.WITHDRAWN
    assert registro.avisos == [
        ("left", comp_id, jugador),
        ("removed", comp_id, jugador),
    ]


async def test_q1_un_admin_tambien():
    uow, _, _, _, inscripcion = await _abierta()

    respuesta = await _quita(uow).execute(_pide(inscripcion.id), UserId(uuid4()), is_admin=True)

    assert respuesta.status == "WITHDRAWN"


async def test_q1_otro_jugador_no():
    uow, _, _, _, inscripcion = await _abierta()

    with pytest.raises(NotCompetitionCreatorError):
        await _quita(uow).execute(_pide(inscripcion.id), UserId(uuid4()))
    assert (await _suya(uow, inscripcion)).status == EnrollmentStatus.APPROVED


async def test_no_existe():
    uow, organizador, _, _, _ = await _abierta()

    with pytest.raises(EnrollmentNotFoundError):
        await _quita(uow).execute(
            RemoveEnrolledPlayerRequestDTO(enrollment_id=uuid4()), organizador
        )


@pytest.mark.parametrize("estado", ["IN_PROGRESS", "COMPLETED"])
async def test_q3_empezada_o_terminada_no(estado):
    uow, organizador, comp_id, _, inscripcion = await _abierta()
    await set_competition_status(uow, comp_id.value, estado)

    with pytest.raises(RemovalNotAllowedError):
        await _quita(uow).execute(_pide(inscripcion.id), organizador)
    assert (await _suya(uow, inscripcion)).status == EnrollmentStatus.APPROVED


@pytest.mark.parametrize("estado", ["ACTIVE", "CLOSED"])
async def test_q3_abierta_o_cerrada_si(estado):
    uow, organizador, comp_id, _, inscripcion = await _abierta()
    await set_competition_status(uow, comp_id.value, estado)

    respuesta = await _quita(uow).execute(_pide(inscripcion.id), organizador)

    assert respuesta.status == "WITHDRAWN"


async def test_q5_el_organizador_no_se_quita_a_si_mismo():
    uow, organizador, comp_id, _, _ = await _abierta()
    async with uow:
        suya = await uow.enrollments.find_by_user_and_competition(organizador, comp_id)

    with pytest.raises(CannotRemoveOrganizerError):
        await _quita(uow).execute(_pide(suya.id), organizador)


async def test_una_solicitud_no_se_quita_se_rechaza():
    uow, organizador, comp_id, _, _ = await _abierta()
    solicitud = Enrollment.request(EnrollmentId.generate(), comp_id, UserId(uuid4()))
    async with uow:
        await uow.enrollments.add(solicitud)

    with pytest.raises(EnrollmentStateError):
        await _quita(uow).execute(_pide(solicitud.id), organizador)


async def _de(uow, comp_id, jugador) -> Enrollment:
    async with uow:
        return await uow.enrollments.find_by_user_and_competition(jugador, comp_id)


async def test_q4_con_equipos_y_sin_partidos_sale_y_se_deshacen():
    uow, comp_id, _, _, equipo_b = await _montar()
    async with uow:
        organizador = (await uow.competitions.find_by_id(comp_id)).creator_id
    inscripcion = await _de(uow, comp_id, equipo_b[1])

    await _quita(uow).execute(_pide(inscripcion.id), organizador)

    async with uow:
        assert await uow.team_assignments.find_by_competition(comp_id) is None


async def test_q4_con_partidos_en_los_que_juega_no_se_deja():
    uow, comp_id, round_id, equipo_a, equipo_b = await _montar()
    async with uow:
        organizador = (await uow.competitions.find_by_id(comp_id)).creator_id
        await uow.matches.add(
            Match.create(
                round_id=round_id,
                match_number=1,
                team_a_players=[_jugador(equipo_a[1])],
                team_b_players=[_jugador(equipo_b[1])],
            )
        )
        await uow.commit()
    inscripcion = await _de(uow, comp_id, equipo_b[1])

    with pytest.raises(PlayerHasMatchesError):
        await _quita(uow).execute(_pide(inscripcion.id), organizador)

    assert (await _suya(uow, inscripcion)).status == EnrollmentStatus.APPROVED
    async with uow:
        assert await uow.team_assignments.find_by_competition(comp_id) is not None


async def test_w_quien_se_retira_de_un_equipo_formado_tambien_los_deshace():
    uow, comp_id, _, _, equipo_b = await _montar()
    inscripcion = await _de(uow, comp_id, equipo_b[1])

    await WithdrawEnrollmentUseCase(uow).execute(
        WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), equipo_b[1]
    )

    async with uow:
        assert await uow.team_assignments.find_by_competition(comp_id) is None


async def test_w_quien_no_estaba_en_ningun_equipo_no_los_deshace():
    uow, comp_id, _, _, _ = await _montar()
    fuera = UserId(uuid4())
    inscripcion = await create_approved_enrollment(uow, comp_id.value, fuera)

    await WithdrawEnrollmentUseCase(uow).execute(
        WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), fuera
    )

    async with uow:
        assert await uow.team_assignments.find_by_competition(comp_id) is not None


async def test_q4_con_partidos_en_los_que_no_juega_tampoco():
    """Decidido el 27 oct: con partidos en cualquier sesión, no se quita a nadie."""
    uow, comp_id, round_id, equipo_a, equipo_b = await _montar()
    async with uow:
        organizador = (await uow.competitions.find_by_id(comp_id)).creator_id
        await uow.matches.add(
            Match.create(
                round_id=round_id,
                match_number=1,
                team_a_players=[_jugador(equipo_a[0])],
                team_b_players=[_jugador(equipo_b[0])],
            )
        )
        await uow.commit()
    inscripcion = await _de(uow, comp_id, equipo_b[1])

    with pytest.raises(PlayerHasMatchesError):
        await _quita(uow).execute(_pide(inscripcion.id), organizador)


@pytest.mark.parametrize("quien", ["organizador", "el_mismo"])
async def test_la_inscripcion_se_relee_con_bloqueo_tras_bloquear_la_competicion(quien):
    """
    Si el jugador se retira mientras el organizador le quita, el segundo en
    entrar tiene que ver la inscripción ya retirada, no la que leyó antes del
    bloqueo (revisor): si no, le «quitaba» a quien se fue solo y se lo decía.
    """
    uow, organizador, _, jugador, inscripcion = await _abierta()
    orden = []
    competicion_original = uow.competitions.find_by_id_for_update
    inscripcion_original = uow.enrollments.find_by_id_for_update

    async def competicion(competition_id):
        orden.append("competicion")
        return await competicion_original(competition_id)

    async def releida(enrollment_id):
        orden.append("inscripcion")
        return await inscripcion_original(enrollment_id)

    uow.competitions.find_by_id_for_update = competicion
    uow.enrollments.find_by_id_for_update = releida

    if quien == "organizador":
        await _quita(uow).execute(_pide(inscripcion.id), organizador)
    else:
        await WithdrawEnrollmentUseCase(uow).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), jugador
        )

    assert orden == ["competicion", "inscripcion"]


@pytest.mark.parametrize("estado", [DraftStatus.PENDING, DraftStatus.IN_PROGRESS])
@pytest.mark.parametrize("quien", ["organizador", "el_mismo"])
async def test_con_la_sala_de_draft_abierta_nadie_sale(estado, quien):
    """Decidido el 27 oct: la sala no se enteraria; es un rato corto, se espera."""
    uow, organizador, comp_id, jugador, inscripcion = await _abierta()
    async with uow:
        await uow.drafts.add(
            Draft(
                id=DraftId.generate(),
                competition_id=comp_id,
                team_a_captain_id=organizador,
                team_b_captain_id=UserId(uuid4()),
                status=estado,
            )
        )

    with pytest.raises(DraftInProgressError):
        if quien == "organizador":
            await _quita(uow).execute(_pide(inscripcion.id), organizador)
        else:
            await WithdrawEnrollmentUseCase(uow).execute(
                WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), jugador
            )

    assert (await _suya(uow, inscripcion)).status == EnrollmentStatus.APPROVED


async def test_la_lista_de_espera_se_rellena_con_el_reloj_de_la_baja(monkeypatch):
    """El mismo `ahora` para las partidas y las franjas (/code-review)."""
    uow, organizador, _, _, inscripcion = await _abierta()
    momentos = []

    async def apunta(self, competicion, round_ids, ahora):
        momentos.append(ahora)

    monkeypatch.setattr(EsperasDeLaCompeticion, "rellenar_varias", apunta)
    reloj = datetime(2030, 1, 2, 3, 4, 5, tzinfo=UTC)

    await RemoveEnrolledPlayerUseCase(uow, reloj=lambda: reloj).execute(
        _pide(inscripcion.id), organizador
    )

    assert momentos == [reloj]
