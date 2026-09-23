"""
Los sobres, por fuera (FE #655).

El agregado ya sabe validar una lista y cruzar dos; aquí se comprueba lo que el
sobre necesita del resto: quién puede entregarlo, con qué jugadores, quién ve
qué y qué pasa al abrirlos.

Las decisiones del 20 sep que fijan esta tabla:

- **Cada capitán entrega la suya sin ver la del otro.** Enseñarla antes es el
  juego entero.
- **Lo que falte al abrir lo rellena la aplicación**, sin pisar al capitán que
  sí entregó.
- **Los enfrentamientos salen de cruzar las dos listas por posición**, que es
  como lo hace la Ryder de verdad.
"""

from uuid import uuid4

import pytest

from src.modules.competition.application.exceptions import (
    NotCompetitionCreatorError,
    RoundNotFoundError,
)
from src.modules.competition.application.services.envelope_pairings import (
    EnvelopePairings,
    EnvelopesNotRevealedError,
)
from src.modules.competition.application.use_cases.get_envelopes_use_case import (
    GetEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.reveal_envelopes_use_case import (
    RevealEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.submit_envelope_use_case import (
    NotATeamCaptainError,
    SubmitEnvelopeUseCase,
)
from src.modules.competition.domain.entities.envelope import (
    EnvelopeAlreadyRevealedError,
    PlayerNotInTeamError,
    TeamNotFullyEnteredError,
)
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
    set_competition_status,
)

pytestmark = pytest.mark.asyncio


async def _montar(formato: MatchFormat = MatchFormat.SINGLES, jugadores: int = 4):
    """Una cerrada con equipos repartidos, sus dos capitanes y una ronda.

    El creador es el capitán A; el primero del equipo B, el capitán B.
    """
    from datetime import date

    uow = InMemoryUnitOfWork()
    creator_id = UserId(uuid4())
    creada = await create_competition(uow, creator_id)
    comp_id = CompetitionId(creada.id)
    resto = [UserId(uuid4()) for _ in range(jugadores - 1)]
    for jugador in resto:
        await create_approved_enrollment(uow, creada.id, jugador)
    await set_competition_status(uow, creada.id, "CLOSED")

    todos = [creator_id, *resto]
    equipo_a = todos[: len(todos) // 2]
    equipo_b = todos[len(todos) // 2 :]
    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        competicion.name_captains(
            equipo_a[0], equipo_b[0], approved_player_ids=todos, has_teams=False
        )
        await uow.competitions.update(competicion)
        await uow.team_assignments.add(
            TeamAssignment.create(
                competition_id=comp_id,
                mode=TeamAssignmentMode.MANUAL,
                team_a_player_ids=equipo_a,
                team_b_player_ids=equipo_b,
            )
        )
        ronda = Round.create(
            competition_id=comp_id,
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=formato,
        )
        await uow.rounds.add(ronda)
        await uow.commit()
    return uow, comp_id, ronda.id, equipo_a, equipo_b


def _entregar(uow):
    return SubmitEnvelopeUseCase(uow)


class TestEntregarElSobre:
    async def test_el_capitan_entrega_la_lista_de_los_suyos(self):
        """
        Given: una competición con equipos y una sesión de individuales
        When: el capitán A entrega su orden
        Then: queda guardado como suyo, sin marcar de automático
        """
        uow, _, round_id, equipo_a, _ = await _montar()

        sobre = await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        assert sobre.team == "A"
        assert sobre.entries == [[equipo_a[1].value], [equipo_a[0].value]]
        assert sobre.automatic is False
        assert sobre.submitted is True

    async def test_el_equipo_sale_de_quien_es_capitan_no_de_lo_que_pida(self):
        """Pedirlo en el cuerpo dejaría entregar el sobre del rival."""
        uow, _, round_id, _, equipo_b = await _montar()

        sobre = await _entregar(uow).execute(
            round_id.value, equipo_b[0], [[str(equipo_b[1].value)], [str(equipo_b[0].value)]]
        )

        assert sobre.team == "B"

    async def test_quien_no_capitanea_nada_no_entrega(self):
        uow, _, round_id, equipo_a, _ = await _montar()

        with pytest.raises(NotATeamCaptainError):
            await _entregar(uow).execute(
                round_id.value, equipo_a[1], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
            )

    async def test_no_se_puede_meter_a_un_jugador_del_otro_equipo(self):
        uow, _, round_id, equipo_a, equipo_b = await _montar()

        with pytest.raises(PlayerNotInTeamError):
            await _entregar(uow).execute(
                round_id.value, equipo_a[0], [[str(equipo_b[0].value)], [str(equipo_a[0].value)]]
            )

    async def test_tienen_que_estar_todos_los_del_equipo(self):
        uow, _, round_id, equipo_a, _ = await _montar()

        with pytest.raises(TeamNotFullyEnteredError):
            await _entregar(uow).execute(round_id.value, equipo_a[0], [[str(equipo_a[0].value)]])

    async def test_una_ronda_que_no_existe(self):
        uow, _, _, equipo_a, _ = await _montar()

        with pytest.raises(RoundNotFoundError):
            await _entregar(uow).execute(uuid4(), equipo_a[0], [[str(equipo_a[0].value)]])

    async def test_se_puede_corregir_hasta_que_se_abren(self):
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        sobre = await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[0].value)], [str(equipo_a[1].value)]]
        )

        assert sobre.entries == [[equipo_a[0].value], [equipo_a[1].value]]

    async def test_abierto_ya_no(self):
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )
        await RevealEnvelopesUseCase(uow).execute(round_id.value, equipo_a[0])

        with pytest.raises(EnvelopeAlreadyRevealedError):
            await _entregar(uow).execute(
                round_id.value, equipo_a[0], [[str(equipo_a[0].value)], [str(equipo_a[1].value)]]
            )


class TestQuienVeQue:
    async def test_el_capitan_ve_el_suyo_y_no_el_del_rival(self):
        """Ver la lista del otro antes de tiempo es el juego entero."""
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )
        await _entregar(uow).execute(
            round_id.value, equipo_b[0], [[str(equipo_b[1].value)], [str(equipo_b[0].value)]]
        )

        vista = await GetEnvelopesUseCase(uow).execute(round_id.value, equipo_a[0])

        assert vista.mine is not None
        assert vista.mine.entries == [[equipo_a[1].value], [equipo_a[0].value]]
        assert vista.rival_submitted is True
        assert vista.rival is None

    async def test_un_espectador_solo_sabe_si_estan_entregados(self):
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        vista = await GetEnvelopesUseCase(uow).execute(round_id.value, equipo_a[1])

        assert vista.mine is None
        assert vista.rival is None
        assert vista.team_a_submitted is True
        assert vista.team_b_submitted is False

    async def test_con_los_dos_entregados_pero_cerrados_no_se_ve_nada(self):
        """El caso peligroso: los dos han entregado y todavía no se han abierto.

        Ahí ya existen las dos listas y cruzarlas es trivial, así que es justo
        cuando la pantalla podría enseñar los enfrentamientos por descuido —y
        sería enseñar la lista del rival antes de tiempo, que es el juego—.
        """
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )

        vista = await GetEnvelopesUseCase(uow).execute(round_id.value, equipo_a[0])

        assert vista.revealed is False
        assert vista.matchups == []
        assert vista.rival is None

    async def test_abiertos_los_ve_todo_el_mundo(self):
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )
        await RevealEnvelopesUseCase(uow).execute(round_id.value, equipo_a[0])

        vista = await GetEnvelopesUseCase(uow).execute(round_id.value, equipo_a[1])

        assert vista.revealed is True
        assert vista.matchups == [
            [[equipo_a[1].value], [equipo_b[1].value]],
            [[equipo_a[0].value], [equipo_b[0].value]],
        ]


class TestAbrirLosSobres:
    async def test_los_enfrentamientos_salen_de_cruzar_por_posicion(self):
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )

        resultado = await RevealEnvelopesUseCase(uow).execute(round_id.value, equipo_a[0])

        assert resultado.matchups == [
            [[equipo_a[1].value], [equipo_b[1].value]],
            [[equipo_a[0].value], [equipo_b[0].value]],
        ]

    async def test_el_que_falta_lo_rellena_la_aplicacion(self):
        """El capitán que se olvidó no deja la sesión sin enfrentamientos."""
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        resultado = await RevealEnvelopesUseCase(uow).execute(round_id.value, equipo_a[0])

        assert len(resultado.matchups) == 2
        assert resultado.filled_automatically == ["B"]

    async def test_y_no_pisa_al_que_si_entrego(self):
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        resultado = await RevealEnvelopesUseCase(uow).execute(round_id.value, equipo_a[0])

        assert [m[0] for m in resultado.matchups] == [
            [equipo_a[1].value],
            [equipo_a[0].value],
        ]

    async def test_los_abre_el_organizador_o_un_capitan_y_nadie_mas(self):
        uow, _, round_id, equipo_a, _ = await _montar()

        with pytest.raises(NotCompetitionCreatorError):
            await RevealEnvelopesUseCase(uow).execute(round_id.value, equipo_a[1])

    async def test_no_se_abren_dos_veces(self):
        uow, _, round_id, equipo_a, _ = await _montar()
        await RevealEnvelopesUseCase(uow).execute(round_id.value, equipo_a[0])

        with pytest.raises(EnvelopeAlreadyRevealedError):
            await RevealEnvelopesUseCase(uow).execute(round_id.value, equipo_a[0])

    async def test_sin_equipos_repartidos_no_hay_sobres(self):
        uow = InMemoryUnitOfWork()
        creator_id = UserId(uuid4())
        creada = await create_competition(uow, creator_id)
        await set_competition_status(uow, creada.id, "CLOSED")

        with pytest.raises(RoundNotFoundError):
            await RevealEnvelopesUseCase(uow).execute(uuid4(), creator_id)


class TestLosPartidosSalenDeLosSobres:
    async def test_el_orden_de_los_sobres_manda_sobre_el_ranking(self):
        """Si no, el sobre es un adorno: el organizador pulsa «generar» y la
        aplicación empareja por hándicap como si nadie hubiera entregado nada.
        """
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )
        await RevealEnvelopesUseCase(uow).execute(round_id.value, equipo_a[0])

        emparejamientos = await EnvelopePairings.de_la_ronda(uow, round_id)

        # En la MISMA forma que los manda el organizador, porque los consume el
        # mismo código: una tupla habría reventado al generar los partidos, y
        # eso no lo ve ningún test de sobres
        assert [(p.team_a_player_ids, p.team_b_player_ids) for p in emparejamientos] == [
            ([equipo_a[1].value], [equipo_b[1].value]),
            ([equipo_a[0].value], [equipo_b[0].value]),
        ]

    async def test_sin_sobres_abiertos_no_hay_nada_que_imponer(self):
        """La sesión que no usa sobres se empareja como siempre."""
        uow, _, round_id, _, _ = await _montar()

        assert await EnvelopePairings.de_la_ronda(uow, round_id) is None

    async def test_con_los_dos_entregados_pero_cerrados_tampoco(self):
        """Fijan los enfrentamientos al ABRIRSE, no al entregarse: hasta
        entonces cualquiera de los dos capitanes puede cambiar su lista."""
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )

        assert await EnvelopePairings.de_la_ronda(uow, round_id) is None

    async def test_con_un_solo_sobre_tampoco(self):
        """Abrir es lo que fija los enfrentamientos: medio sobre no fija nada."""
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        assert await EnvelopePairings.de_la_ronda(uow, round_id) is None

    async def test_con_un_sobre_entregado_sin_abrir_no_se_empareja_por_ranking(self):
        """Generar ahí tiraría a la basura la lista que el capitán sí entregó.

        `de_la_ronda` devuelve None mientras estén cerrados, así que la
        generación caería en el emparejamiento por hándicap sin avisar: hay que
        decir que primero se abren.
        """
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        async with uow:
            with pytest.raises(EnvelopesNotRevealedError):
                await EnvelopePairings.comprobar_que_no_hay_sobres_sin_abrir(uow, round_id)

    async def test_sin_ningun_sobre_entregado_se_empareja_como_siempre(self):
        uow, _, round_id, _, _ = await _montar()

        async with uow:
            await EnvelopePairings.comprobar_que_no_hay_sobres_sin_abrir(uow, round_id)
