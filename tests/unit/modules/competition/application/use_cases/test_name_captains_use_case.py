"""
Tests de NameCaptainsUseCase (BE #320).

Nombrar a los capitanes cierra las inscripciones. Los capitanes siempre juegan:
son dos de los inscritos aprobados, uno por equipo, y el organizador puede
nombrarse a si mismo. Con un numero impar se avisa y se deja seguir: quedarse
atascado la vispera es peor que un torneo desigual.
"""

from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import NameCaptainsRequestDTO
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.name_captains_use_case import (
    NameCaptainsUseCase,
)
from src.modules.competition.domain.entities.competition import (
    CaptainNotEnrolledError,
    CaptainsLockedError,
    CompetitionStateError,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
    set_competition_status,
)

pytestmark = pytest.mark.asyncio


async def _montar(inscritos: int = 4):
    """Una competición abierta con `inscritos` aprobados, contando al creador.

    Crearla ya inscribe al organizador; los demás se devuelven en la lista.
    """
    uow = InMemoryUnitOfWork()
    creator_id = UserId(uuid4())
    creada = await create_competition(uow, creator_id)
    jugadores = [UserId(uuid4()) for _ in range(inscritos - 1)]
    for jugador in jugadores:
        await create_approved_enrollment(uow, creada.id, jugador)
    return uow, creada.id, creator_id, jugadores


def _peticion(competition_id, a: UserId, b: UserId) -> NameCaptainsRequestDTO:
    """La petición de nombrar a `a` y `b` capitanes de esa competición."""
    return NameCaptainsRequestDTO(
        competition_id=competition_id, team_a_captain_id=a.value, team_b_captain_id=b.value
    )


async def _competicion(uow, competition_id):
    """La competición tal como quedó guardada."""
    async with uow:
        return await uow.competitions.find_by_id(CompetitionId(competition_id))


async def test_nombrarlos_cierra_las_inscripciones_y_los_guarda():
    """
    Given: una abierta con cuatro inscritos
    When: el creador nombra a dos de ellos
    Then: queda CLOSED con los dos guardados, y la respuesta lo dice
    """
    uow, comp_id, creator_id, (ana, bea, *_) = await _montar(inscritos=4)

    respuesta = await NameCaptainsUseCase(uow).execute(_peticion(comp_id, ana, bea), creator_id)

    competicion = await _competicion(uow, comp_id)
    assert competicion.status == CompetitionStatus.CLOSED
    assert (competicion.team_a_captain_id, competicion.team_b_captain_id) == (ana, bea)
    assert respuesta.status == "CLOSED"
    assert (respuesta.team_a_captain_id, respuesta.team_b_captain_id) == (ana.value, bea.value)


@pytest.mark.parametrize(
    ("inscritos", "desigual"), [(4, False), (5, True), (12, False), (11, True)]
)
async def test_con_numeros_impares_avisa_y_deja_seguir(inscritos, desigual):
    """Con once, los equipos salen de 6 y 5: se avisa, pero se nombran igual."""
    uow, comp_id, creator_id, (ana, bea, *_) = await _montar(inscritos=inscritos)

    respuesta = await NameCaptainsUseCase(uow).execute(_peticion(comp_id, ana, bea), creator_id)

    assert respuesta.total_players == inscritos
    assert respuesta.uneven_teams is desigual
    assert (await _competicion(uow, comp_id)).status == CompetitionStatus.CLOSED


async def test_el_organizador_puede_nombrarse_a_si_mismo():
    """Entre amigos, quien organiza suele tirar del grupo."""
    uow, comp_id, creator_id, (ana, *_) = await _montar(inscritos=3)

    await NameCaptainsUseCase(uow).execute(_peticion(comp_id, creator_id, ana), creator_id)

    assert (await _competicion(uow, comp_id)).team_a_captain_id == creator_id


async def test_un_admin_puede_nombrarlos_en_la_de_otro():
    """
    Given: la competición de otro
    When: un admin nombra capitanes
    Then: se nombran y queda cerrada
    """
    uow, comp_id, _, (ana, bea, *_) = await _montar()

    await NameCaptainsUseCase(uow).execute(
        _peticion(comp_id, ana, bea), UserId(uuid4()), is_admin=True
    )

    assert (await _competicion(uow, comp_id)).status == CompetitionStatus.CLOSED


async def test_otro_usuario_no_puede():
    """
    Given: una abierta
    When: un jugador que no es el creador nombra capitanes
    Then: se rechaza y sigue abierta
    """
    uow, comp_id, _, (ana, bea, *_) = await _montar()

    with pytest.raises(NotCompetitionCreatorError):
        await NameCaptainsUseCase(uow).execute(_peticion(comp_id, ana, bea), ana)

    assert (await _competicion(uow, comp_id)).status == CompetitionStatus.ACTIVE


async def test_una_competicion_que_no_existe():
    """
    Given: un identificador que no existe
    When: se nombran capitanes
    Then: se dice que no existe
    """
    uow = InMemoryUnitOfWork()

    with pytest.raises(CompetitionNotFoundError):
        await NameCaptainsUseCase(uow).execute(
            _peticion(uuid4(), UserId(uuid4()), UserId(uuid4())), UserId(uuid4()), is_admin=True
        )


@pytest.mark.parametrize("como", ["sin inscripcion", "pidio plaza", "invitado", "se retiro"])
async def test_un_capitan_tiene_que_ser_un_inscrito_aprobado(como):
    """Los capitanes siempre juegan: dos de los inscritos, no dos personas mas."""
    uow, comp_id, creator_id, (ana, *_) = await _montar()
    ajeno = UserId(uuid4())
    if como != "sin inscripcion":
        if como == "invitado":
            inscripcion = Enrollment.invite(
                id=EnrollmentId.generate(), competition_id=CompetitionId(comp_id), user_id=ajeno
            )
        else:
            inscripcion = Enrollment.request(
                id=EnrollmentId.generate(), competition_id=CompetitionId(comp_id), user_id=ajeno
            )
        if como == "se retiro":
            inscripcion.approve()
            inscripcion.withdraw()
        async with uow:
            await uow.enrollments.add(inscripcion)
            await uow.commit()

    with pytest.raises(CaptainNotEnrolledError):
        await NameCaptainsUseCase(uow).execute(_peticion(comp_id, ana, ajeno), creator_id)

    competicion = await _competicion(uow, comp_id)
    assert competicion.status == CompetitionStatus.ACTIVE
    assert competicion.team_a_captain_id is None


async def test_el_capitan_a_tambien_se_comprueba():
    """Que no se valide solo el segundo."""
    uow, comp_id, creator_id, (_, bea, *_) = await _montar()

    with pytest.raises(CaptainNotEnrolledError):
        await NameCaptainsUseCase(uow).execute(_peticion(comp_id, UserId(uuid4()), bea), creator_id)


async def test_con_los_equipos_repartidos_ya_no_se_cambian():
    """
    Given: una cerrada con los equipos ya repartidos
    When: se nombran otros capitanes
    Then: se rechaza: habría que rehacer los equipos
    """
    uow, comp_id, creator_id, (ana, bea, carla, dani) = await _montar(inscritos=5)
    await set_competition_status(uow, comp_id, "CLOSED")
    async with uow:
        await uow.team_assignments.add(
            TeamAssignment.create(
                competition_id=CompetitionId(comp_id),
                mode=TeamAssignmentMode.MANUAL,
                team_a_player_ids=[ana, bea],
                team_b_player_ids=[carla, dani],
            )
        )
        await uow.commit()

    with pytest.raises(CaptainsLockedError):
        await NameCaptainsUseCase(uow).execute(_peticion(comp_id, ana, carla), creator_id)


async def test_en_juego_no_se_nombran():
    """
    Given: una competición en juego
    When: se nombran capitanes
    Then: se rechaza por el estado
    """
    uow, comp_id, creator_id, (ana, bea, *_) = await _montar()
    await set_competition_status(uow, comp_id, "IN_PROGRESS")

    with pytest.raises(CompetitionStateError):
        await NameCaptainsUseCase(uow).execute(_peticion(comp_id, ana, bea), creator_id)


async def test_bloquea_la_fila_de_la_competicion():
    """Como el cupo: una inscripcion aprobada a la vez no puede colarse en el recuento."""
    uow, comp_id, creator_id, (ana, bea, *_) = await _montar()
    llamadas = []
    original = uow.competitions.find_by_id_for_update

    async def espia(competition_id):
        """Anota con qué competición se pidió el bloqueo y deja hacer al original."""
        llamadas.append(competition_id)
        return await original(competition_id)

    uow.competitions.find_by_id_for_update = espia

    await NameCaptainsUseCase(uow).execute(_peticion(comp_id, ana, bea), creator_id)

    assert llamadas == [CompetitionId(comp_id)]
