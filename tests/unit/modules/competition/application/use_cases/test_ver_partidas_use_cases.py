"""
Ver las partidas de una franja y las mías (#251, PR 4; D8 del 9 oct 2026).

Cualquiera con sesión, como los partidos de la Ryder. `editable` dice si el
organizador aún puede tocarlas; mirar nunca falla por eso.

| Caso                                                     | Resultado                         |
|----------------------------------------------------------|-----------------------------------|
| Un jugador mira la franja                                | La vista, igual que al generar    |
| Antes de generar                                         | Sin partidas, todos en unassigned |
| Abiertas / tras la 1.ª salida / una empezada / sin zona  | editable: false, sin error        |
| Con la primera fuera y la segunda sin salir (#544)       | editable: false (generar, como    |
|                                                          |   siempre); can_change por partida|
| Una con golpes antes de su hora, la siguiente sin salir  | can_change: false / true          |
| Justo a la hora de la segunda                            | Las dos fuera                     |
| unassigned                                               | Ni retirados ni ya colocados      |
| Una sesión de Ryder / una franja que no existe           | PartidasError / RoundNotFound     |
| Mis partidas, en dos franjas                             | Las dos, por día y hora           |
| Mis partidas, sin ninguna                                | []                                |
"""

from datetime import datetime, time, timedelta

import pytest

from src.modules.competition.application.exceptions import PartidasError, RoundNotFoundError
from src.modules.competition.application.use_cases.partidas_use_case import (
    MisPartidasUseCase,
    VerPartidasUseCase,
)
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    A_LA_PRIMERA_SALIDA,
    VIERNES,
    _Escenario,
)

pytestmark = pytest.mark.asyncio


def _ver(escenario: _Escenario) -> VerPartidasUseCase:
    return VerPartidasUseCase(
        uow=escenario.uow,
        zonas=escenario.zonas,
        user_repository=escenario.usuarios,
        reloj=lambda: escenario.ahora,
    )


async def _vista(escenario: _Escenario, franja=None, quien=None, is_admin=False):
    return await _ver(escenario).execute(
        (franja or escenario.manana).id.value, quien or escenario.creador, is_admin
    )


async def test_a_player_sees_the_same_as_the_organiser_but_cannot_edit():
    # `editable` dice «puedes editar»: a un jugador, siempre no (#541)
    escenario = _Escenario()
    await escenario.guardar()
    jugadores = [await escenario.con_plaza(f"{h}.0") for h in (3, 2, 1)]
    generada = await escenario.generar()

    vista = await _vista(escenario, quien=jugadores[0])

    assert generada.editable
    assert generada.can_add_group
    assert vista.editable is False
    # Ni las partidas ni una nueva: nada es «puedes editar» para un jugador (#544)
    assert vista.can_add_group is False
    assert [g.can_change for g in vista.groups] == [False]
    assert {p.user_id for p in vista.groups[0].players} == {u.value for u in jugadores}


async def test_an_admin_can_edit():
    escenario = _Escenario()
    await escenario.guardar()
    jugador = await escenario.con_plaza("3.0")

    assert (await _vista(escenario, quien=jugador, is_admin=True)).editable


async def test_before_generating_everybody_is_unassigned():
    escenario = _Escenario()
    await escenario.guardar()
    jugadores = [await escenario.con_plaza(f"{h}.0") for h in (3, 2)]

    vista = await _vista(escenario)

    assert vista.groups == []
    assert [p.name for p in vista.unassigned_players] == ["Jugador 3.0", "Jugador 2.0"]
    assert [p.user_id for p in vista.unassigned_players] == [u.value for u in jugadores]
    assert vista.editable


# /code-review de la release social 2: antes de generar, «sin partida» eran todos
# los que tienen plaza, con nombre, para cualquiera. Ahora, lo que deja la regla
class _Amigos:
    def __init__(self, de):
        self._de = de

    async def ids_de_los_amigos(self, user_id):
        return frozenset(self._de.get(user_id, set()))


async def _vista_de(escenario, quien, amigos, email=None):
    return await VerPartidasUseCase(
        uow=escenario.uow,
        zonas=escenario.zonas,
        user_repository=escenario.usuarios,
        reloj=lambda: escenario.ahora,
        amigos=amigos,
    ).execute(escenario.manana.id.value, quien, False, email=email)


async def test_before_generating_a_player_of_a_public_one_sees_only_friends_unassigned():
    escenario = _Escenario()
    escenario.competicion._visibility = Visibility.PUBLIC
    await escenario.guardar()
    yo, amiga, _otra = [await escenario.con_plaza(f"{h}.0") for h in (3, 2, 1)]

    vista = await _vista_de(escenario, yo, _Amigos({yo: {amiga}}))

    assert [p.user_id for p in vista.unassigned_players] == [yo.value, amiga.value]


async def test_before_generating_an_outsider_of_a_private_one_sees_nobody_unassigned():
    escenario = _Escenario()
    await escenario.guardar()
    for h in (3, 2):
        await escenario.con_plaza(f"{h}.0")

    vista = await _vista_de(escenario, UserId.generate(), _Amigos({}))

    assert vista.unassigned_players == []


async def test_before_generating_invited_by_email_to_a_private_one_sees_friends():
    escenario = _Escenario()
    await escenario.guardar()
    yo, amiga = UserId.generate(), await escenario.con_plaza("3.0")
    await escenario.con_plaza("2.0")
    async with escenario.uow:
        await escenario.uow.invitations.add(
            Invitation(
                id=InvitationId.generate(),
                competition_id=escenario.competicion.id,
                inviter_id=escenario.creador,
                invitee_email="yo@test.com",
                status=InvitationStatus.PENDING,
                expires_at=datetime.now() + timedelta(days=7),
            )
        )
    amigos = _Amigos({yo: {amiga}})

    con_correo = await _vista_de(escenario, yo, amigos, email="yo@test.com")
    sin_correo = await _vista_de(escenario, yo, amigos)

    assert [p.user_id for p in con_correo.unassigned_players] == [amiga.value]
    assert sin_correo.unassigned_players == []


async def test_the_organiser_still_sees_everybody_unassigned():
    escenario = _Escenario()
    escenario.competicion._visibility = Visibility.PUBLIC
    await escenario.guardar()
    jugadores = [await escenario.con_plaza(f"{h}.0") for h in (3, 2)]

    vista = await _vista_de(escenario, escenario.creador, _Amigos({}))

    assert [p.user_id for p in vista.unassigned_players] == [u.value for u in jugadores]


async def test_unassigned_leaves_out_the_withdrawn_and_the_placed():
    escenario = _Escenario()
    await escenario.guardar()
    for h in (3, 2):
        await escenario.con_plaza(f"{h}.0")
    await escenario.generar()
    tarde = await escenario.con_plaza("9.0")
    await escenario.con_plaza("8.0", status=EnrollmentStatus.WITHDRAWN)

    assert [p.user_id for p in (await _vista(escenario)).unassigned_players] == [tarde.value]


@pytest.mark.parametrize(
    ("status", "zona", "ahora"),
    [
        pytest.param(CompetitionStatus.ACTIVE, "Europe/Madrid", None, id="inscripciones abiertas"),
        pytest.param(CompetitionStatus.CLOSED, "Europe/Madrid", A_LA_PRIMERA_SALIDA, id="salió"),
        pytest.param(CompetitionStatus.CLOSED, None, None, id="sin zona"),
    ],
)
async def test_not_editable_without_failing(status, zona, ahora):
    escenario = _Escenario(status=status, zona=zona)
    if ahora:
        escenario.ahora = ahora
    await escenario.guardar()

    vista = await _vista(escenario)

    assert vista.editable is False


async def test_not_editable_once_a_group_started():
    escenario = _Escenario()
    await escenario.guardar()
    for h in (3, 2):
        await escenario.con_plaza(f"{h}.0")
    await escenario.generar()
    (partida,) = await escenario.uow.partidas.de_la_franja(escenario.manana.id)
    await escenario.uow.partidas.guardar(
        [
            Partida(
                id=partida.id,
                competition_id=partida.competition_id,
                round_id=partida.round_id,
                numero=partida.numero,
                jugadores=partida.jugadores,
                marcadores=partida.marcadores,
                estado=EstadoPartida.IN_PROGRESS,
            )
        ]
    )

    vista = await _vista(escenario)

    assert vista.editable is False
    assert vista.groups[0].status == "IN_PROGRESS"


async def test_with_the_first_group_out_the_second_can_still_be_touched():
    from datetime import timedelta

    escenario = _Escenario()
    await escenario.guardar()
    for h in range(7, 0, -1):
        await escenario.con_plaza(f"{h}.0")
    await escenario.generar()
    escenario.ahora = A_LA_PRIMERA_SALIDA + timedelta(minutes=5)

    vista = await _vista(escenario)

    # `editable` no cambia de significado: el front de producción lo usa para generar
    assert vista.editable is False
    assert [g.can_change for g in vista.groups] == [False, True]
    assert vista.can_add_group is True


async def test_a_group_with_strokes_before_its_time_is_out():
    escenario = _Escenario()
    await escenario.guardar()
    for h in range(7, 0, -1):
        await escenario.con_plaza(f"{h}.0")
    await escenario.generar()
    primera, _ = sorted(
        await escenario.uow.partidas.de_la_franja(escenario.manana.id), key=lambda p: p.numero
    )
    empezada = await escenario.uow.partidas.find_by_id(primera.id)
    empezada.empezar()
    await escenario.uow.partidas.guardar([empezada])

    vista = await _vista(escenario)

    assert [g.can_change for g in vista.groups] == [False, True]


async def test_right_at_the_second_tee_time_both_are_out():
    from datetime import timedelta

    escenario = _Escenario()
    await escenario.guardar()
    for h in range(7, 0, -1):
        await escenario.con_plaza(f"{h}.0")
    await escenario.generar()
    escenario.ahora = A_LA_PRIMERA_SALIDA + timedelta(minutes=10)

    vista = await _vista(escenario)

    assert [g.can_change for g in vista.groups] == [False, False]
    # Quedan salidas libres por llegar (9:20…10:00): aún cabe una nueva
    assert vista.can_add_group is True


async def test_no_new_group_once_the_sheet_is_over():
    from datetime import timedelta

    escenario = _Escenario()
    await escenario.guardar()
    for h in range(7, 0, -1):
        await escenario.con_plaza(f"{h}.0")
    await escenario.generar()
    escenario.ahora = A_LA_PRIMERA_SALIDA + timedelta(minutes=65)

    assert (await _vista(escenario)).can_add_group is False


async def test_a_ryder_session_and_a_window_that_does_not_exist():
    escenario = _Escenario()
    await escenario.guardar()
    sesion = Round.create(
        competition_id=escenario.competicion.id,
        golf_course_id=GolfCourseId.generate(),
        round_date=VIERNES,
        session_type=SessionType.EVENING,
        match_format=MatchFormat.SINGLES,
    )
    async with escenario.uow:
        await escenario.uow.rounds.add(sesion)

    with pytest.raises(PartidasError):
        await _vista(escenario, sesion)
    with pytest.raises(RoundNotFoundError):
        await _ver(escenario).execute(RoundId.generate().value, escenario.creador, False)


async def test_my_groups_in_two_windows_by_day_and_time():
    escenario = _Escenario()
    await escenario.guardar()
    yo = await escenario.con_plaza("5.0", franja=escenario.tarde)
    await escenario.con_plaza("6.0", franja=escenario.tarde)
    for h in (3, 2):
        await escenario.con_plaza(f"{h}.0")
    await escenario.generar()
    await escenario.generar(franja=escenario.tarde)
    # Y otra franja, por la mañana, en la que también juega
    temprano = Round.create_franja(
        competition_id=escenario.competicion.id,
        golf_course_id=GolfCourseId.generate(),
        round_date=VIERNES,
        session_type=SessionType.EVENING,
        hoja_de_salidas=HojaDeSalidas(time(7, 0), time(8, 0), 10, 4),
    )
    async with escenario.uow:
        await escenario.uow.rounds.add(temprano)
    tarde_partida = (await escenario.uow.partidas.de_la_franja(escenario.tarde.id))[0]
    yo_jugador = next(j for j in tarde_partida.jugadores if j.user_id == yo)
    otro = next(j for j in tarde_partida.jugadores if j.user_id != yo)
    await escenario.uow.partidas.anadir(
        [Partida.crear(escenario.competicion.id, temprano.id, 1, [yo_jugador, otro])]
    )

    mias = await MisPartidasUseCase(uow=escenario.uow, user_repository=escenario.usuarios).execute(
        escenario.competicion.id.value, yo
    )

    assert [(g.round_id, g.group.tee_time) for g in mias.groups] == [
        (temprano.id.value, "07:00"),
        (escenario.tarde.id.value, "15:00"),
    ]
    assert mias.groups[1].session_type == "AFTERNOON"
    assert {p.user_id for p in mias.groups[1].group.players} == {yo.value, otro.user_id.value}


async def test_my_groups_without_any():
    escenario = _Escenario()
    await escenario.guardar()

    mias = await MisPartidasUseCase(uow=escenario.uow, user_repository=escenario.usuarios).execute(
        escenario.competicion.id.value, UserId.generate()
    )

    assert mias.groups == []


class _NombresDeCampos:
    def __init__(self, nombres):
        self.nombres = nombres
        self.pedidos = []

    async def find_names_by_ids(self, ids):
        self.pedidos.append(sorted(str(i) for i in ids))
        return {str(i): self.nombres[str(i)] for i in ids if str(i) in self.nombres}


async def test_my_groups_carry_their_course_id_and_name_in_one_query():
    """
    GIVEN: Mis partidas en dos franjas de campos distintos (uno ya no está)
    WHEN: Pido mis partidas
    THEN: Cada una lleva el id y el nombre de su campo (null si no está), en una
          sola consulta de nombres (BE #532, 16 oct: «Mis Próximos Partidos»)
    """
    escenario = _Escenario()
    await escenario.guardar()
    yo = await escenario.con_plaza("5.0", franja=escenario.tarde)
    await escenario.con_plaza("6.0", franja=escenario.tarde)
    await escenario.generar(franja=escenario.tarde)
    otro_campo = GolfCourseId.generate()
    temprano = Round.create_franja(
        competition_id=escenario.competicion.id,
        golf_course_id=otro_campo,
        round_date=VIERNES,
        session_type=SessionType.EVENING,
        hoja_de_salidas=HojaDeSalidas(time(7, 0), time(8, 0), 10, 4),
    )
    async with escenario.uow:
        await escenario.uow.rounds.add(temprano)
    tarde_partida = (await escenario.uow.partidas.de_la_franja(escenario.tarde.id))[0]
    yo_jugador = next(j for j in tarde_partida.jugadores if j.user_id == yo)
    otro = next(j for j in tarde_partida.jugadores if j.user_id != yo)
    await escenario.uow.partidas.anadir(
        [Partida.crear(escenario.competicion.id, temprano.id, 1, [yo_jugador, otro])]
    )
    campos = _NombresDeCampos({str(escenario.tarde.golf_course_id): "Golf de Meis - Par 72"})

    mias = await MisPartidasUseCase(
        uow=escenario.uow, user_repository=escenario.usuarios, golf_courses=campos
    ).execute(escenario.competicion.id.value, yo)

    assert [(g.golf_course_id, g.golf_course_name) for g in mias.groups] == [
        (otro_campo.value, None),
        (escenario.tarde.golf_course_id.value, "Golf de Meis - Par 72"),
    ]
    assert campos.pedidos == [sorted([str(otro_campo), str(escenario.tarde.golf_course_id)])]


async def test_my_groups_without_a_courses_repository_carry_no_name():
    """
    GIVEN: Mis partidas, sin repositorio de campos
    WHEN: Pido mis partidas
    THEN: Llevan el id del campo y el nombre a null, sin error
    """
    escenario = _Escenario()
    await escenario.guardar()
    yo = await escenario.con_plaza("5.0", franja=escenario.tarde)
    await escenario.con_plaza("6.0", franja=escenario.tarde)
    await escenario.generar(franja=escenario.tarde)

    mias = await MisPartidasUseCase(uow=escenario.uow, user_repository=escenario.usuarios).execute(
        escenario.competicion.id.value, yo
    )

    assert mias.groups
    assert all(g.golf_course_name is None for g in mias.groups)
    assert all(g.golf_course_id == escenario.tarde.golf_course_id.value for g in mias.groups)


async def test_my_groups_without_any_do_not_ask_for_course_names():
    """
    GIVEN: Un jugador sin partidas
    WHEN: Pide sus partidas
    THEN: Vacío, y sin consultar nombres de campos
    """
    escenario = _Escenario()
    await escenario.guardar()
    campos = _NombresDeCampos({})

    mias = await MisPartidasUseCase(
        uow=escenario.uow, user_repository=escenario.usuarios, golf_courses=campos
    ).execute(escenario.competicion.id.value, UserId.generate())

    assert mias.groups == []
    assert campos.pedidos == []


# Tabla del 27 oct 2026: en una privada, las partidas solo las ve quien está
# dentro; de fuera, con la llave de su Actividad, la de su amigo y nada más
class _Eventos:
    def __init__(self, *amigos):
        self.amigos = frozenset(amigos)

    async def amigos_con_evento_en(self, user_id, competition_id):
        return self.amigos


async def _privada_con_dos_partidas(visibilidad=Visibility.PRIVATE):
    escenario = _Escenario()
    escenario.competicion._visibility = visibilidad
    await escenario.guardar()
    jugadores = [await escenario.con_plaza(f"{h}.0") for h in (8, 7, 6, 5, 4, 3, 2, 1)]
    generada = await escenario.generar()
    assert len(generada.groups) == 2
    return escenario, jugadores, generada


async def _grupos_que_ve(escenario, quien, eventos):
    vista = await VerPartidasUseCase(
        uow=escenario.uow,
        zonas=escenario.zonas,
        user_repository=escenario.usuarios,
        reloj=lambda: escenario.ahora,
        eventos=eventos,
    ).execute(escenario.manana.id.value, quien, False)
    return [g.number for g in vista.groups]


async def test_6_an_outsider_of_a_private_one_sees_no_groups():
    escenario, _, _ = await _privada_con_dos_partidas()

    assert await _grupos_que_ve(escenario, UserId.generate(), _Eventos()) == []


async def test_7_with_a_friends_event_only_the_friends_group():
    escenario, _, generada = await _privada_con_dos_partidas()
    amigo = UserId(str(generada.groups[1].players[0].user_id))

    assert await _grupos_que_ve(escenario, UserId.generate(), _Eventos(amigo)) == [2]


async def test_2_an_approved_player_of_a_private_one_sees_every_group():
    escenario, jugadores, _ = await _privada_con_dos_partidas()

    assert await _grupos_que_ve(escenario, jugadores[0], _Eventos()) == [1, 2]


async def test_d8_an_outsider_of_a_public_one_still_sees_every_group():
    escenario, _, _ = await _privada_con_dos_partidas(Visibility.PUBLIC)

    assert await _grupos_que_ve(escenario, UserId.generate(), _Eventos()) == [1, 2]


async def test_5_a_withdrawn_player_still_sees_his_own_group_only():
    """/code-review: quien se retiró tras jugar sigue viendo su partida."""
    escenario, _, generada = await _privada_con_dos_partidas()
    yo = UserId(str(generada.groups[0].players[0].user_id))
    async with escenario.uow:
        suya = await escenario.uow.enrollments.find_by_user_and_competition(
            yo, escenario.competicion.id
        )
        suya.withdraw()
        await escenario.uow.enrollments.update(suya)

    assert await _grupos_que_ve(escenario, yo, _Eventos()) == [1]
