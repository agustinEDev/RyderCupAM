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

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from src.modules.competition.application.exceptions import (
    NotCompetitionCreatorError,
    NotCompetitionParticipantError,
    RoundNotFoundError,
)
from src.modules.competition.application.services.envelope_desk import (
    RoundAlreadyScheduledError,
)
from src.modules.competition.application.services.envelope_pairings import (
    EnvelopePairings,
    EnvelopesDecideThePairingsError,
    EnvelopesNotRevealedError,
)
from src.modules.competition.application.use_cases.get_envelopes_use_case import (
    GetEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.reveal_envelopes_use_case import (
    RevealEnvelopesUseCase,
    RivalEnvelopeMissingError,
)
from src.modules.competition.application.use_cases.submit_envelope_use_case import (
    NotATeamCaptainError,
    SubmitEnvelopeUseCase,
)
from src.modules.competition.domain.entities.competition import TeamsNotAssignedError
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.envelope import (
    EmptyEnvelopeError,
    EnvelopeAlreadyRevealedError,
    PlayerNotInTeamError,
    TeamNotFullyEnteredError,
)
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
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


async def _crear_sesion_anterior(uow, comp_id):
    """Una sesión de mañana el día antes, todavía sin partidos generados."""
    from datetime import date as _date

    async with uow:
        ronda = Round.create(
            competition_id=comp_id,
            golf_course_id=GolfCourseId.generate(),
            round_date=_date(2026, 5, 31),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        ronda.mark_teams_assigned()
        await uow.rounds.add(ronda)
        await uow.commit()
    return ronda.id


async def _marcar_partidos_generados(uow, round_id):
    """Deja la sesión como queda cuando ya se han generado sus partidos."""
    async with uow:
        ronda = await uow.rounds.find_by_id(round_id)
        ronda.mark_matches_generated()
        await uow.rounds.update(ronda)
        await uow.commit()


async def _cambiar_formato(uow, comp_id, round_id, organizador, formato):
    """Cambia el formato de la sesión, como hace el organizador desde la agenda."""
    from src.modules.competition.application.dto.round_match_dto import UpdateRoundRequestDTO
    from src.modules.competition.application.use_cases.update_round_use_case import (
        UpdateRoundUseCase,
    )

    return await UpdateRoundUseCase(uow).execute(
        UpdateRoundRequestDTO(round_id=round_id.value, match_format=formato), organizador
    )


async def _dar_handicap_de_usuario(uow, user_id, handicap):
    """Deja al jugador con ese hándicap en su perfil."""
    _HANDICAPS_DE_PERFIL[user_id] = handicap


async def _dar_handicap_propio(uow, competition_id, user_id, handicap):
    """Le pone hándicap propio en ESTA competición, que manda sobre el perfil."""
    async with uow:
        for inscripcion in await uow.enrollments.find_by_competition(competition_id):
            if inscripcion.user_id == user_id:
                inscripcion.set_custom_handicap(handicap)
                await uow.enrollments.update(inscripcion)
        await uow.commit()


_HANDICAPS_DE_PERFIL: dict = {}


class _Reloj:
    """El reloj del servidor, que en los tests se mueve a mano."""

    def __init__(self, ahora):
        self._ahora = ahora

    def __call__(self):
        return self._ahora


class _Zona:
    """La zona del campo donde se juega.

    `de_la_sesion` es la del campo de esa ronda, que en una competición de
    varios campos NO tiene por qué ser la del primero.
    """

    def __init__(self, zona="Europe/Madrid", de_la_sesion="igual"):
        self._zona = zona
        self._de_la_sesion = zona if de_la_sesion == "igual" else de_la_sesion

    async def for_competition(self, competition):
        return self._zona

    async def for_course(self, golf_course_id):
        return self._de_la_sesion


class _RepoUsuarios:
    """Un repositorio de usuarios con el hándicap que tenga cada uno."""

    class _Usuario:
        def __init__(self, user_id, handicap):
            self.id = user_id
            self.handicap = handicap

        def display_name_or_legal(self, nombre_legal: bool) -> str:
            return f"Jugador {str(self.id.value)[:4]}"

    async def find_by_id(self, user_id):
        handicap = _HANDICAPS_DE_PERFIL.get(user_id)
        return self._Usuario(user_id, _Handicap(handicap) if handicap is not None else None)

    async def find_by_ids(self, user_ids):
        encontrados = []
        for uid in user_ids:
            usuario = await self.find_by_id(uid)
            if usuario:
                encontrados.append(usuario)
        return encontrados


class _Handicap:
    """Lo justo que la aplicación le pide a un hándicap: su valor."""

    def __init__(self, value):
        self.value = value


async def _montar(
    formato: MatchFormat = MatchFormat.SINGLES,
    jugadores: int = 4,
    con_equipos: bool = True,
):
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
    # Con un número impar, el jugador de más va al equipo A: así el caso de
    # «A se puede emparejar y B no» se puede montar, que es el orden en el que
    # el revelado los toca
    mitad = (len(todos) + 1) // 2
    equipo_a = todos[:mitad]
    equipo_b = todos[mitad:]
    _HANDICAPS_DE_PERFIL.clear()
    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        competicion.name_captains(
            equipo_a[0], equipo_b[0], approved_player_ids=todos, has_teams=False
        )
        await uow.competitions.update(competicion)
        if con_equipos:
            await uow.team_assignments.add(
                TeamAssignment.create(
                    competition_id=comp_id,
                    # DRAFT y no MANUAL: es de donde vienen estos equipos, y es
                    # el único modo que admite la diferencia de un jugador
                    mode=TeamAssignmentMode.DRAFT,
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
        if con_equipos:
            # Como la deja el reparto: al asignar equipos, las rondas que los
            # esperaban pasan a esperar partidos
            ronda.mark_teams_assigned()
        await uow.rounds.add(ronda)
        await uow.commit()
    return uow, comp_id, ronda.id, equipo_a, equipo_b


# La ronda del montaje es del 1 de junio y de mañana, así que su plazo vence a
# las 00:00 de ese día: este reloj está después
_PASADO_EL_PLAZO = datetime(2026, 6, 1, 1, 0, tzinfo=ZoneInfo("Europe/Madrid"))
# El día antes: el plazo todavía no ha vencido
_ANTES = datetime(2026, 5, 31, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))


async def _abrir_por_plazo(uow, round_id, quien):
    """Abre los sobres como lo hace la vida real: venciendo el plazo.

    Ya no hay forma de forzarlo a mano con un sobre fuera (23 sep), así que el
    relleno automático solo ocurre por aquí.
    """
    return await GetEnvelopesUseCase(
        uow, _RepoUsuarios(), _Reloj(_PASADO_EL_PLAZO), _Zona()
    ).execute(round_id.value, quien)


def _entregar(uow):
    return SubmitEnvelopeUseCase(uow, _RepoUsuarios())


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
        await _abrir_por_plazo(uow, round_id, equipo_a[0])

        with pytest.raises(EnvelopeAlreadyRevealedError):
            await _entregar(uow).execute(
                round_id.value, equipo_a[0], [[str(equipo_a[0].value)], [str(equipo_a[1].value)]]
            )


class TestElRellenoUsaElHandicapDeVerdad:
    async def test_ordena_por_el_handicap_del_jugador_y_no_solo_por_el_propio(self):
        """`custom_handicap` casi siempre es None: ordenando solo por él, el
        sobre automático sale en el orden de la lista y no por hándicap.
        """
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        # Al equipo B, hándicaps de usuario en orden inverso al del reparto
        for i, jugador in enumerate(equipo_b):
            await _dar_handicap_de_usuario(uow, jugador, Decimal(str(30 - i * 10)))
        await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        vista = await _abrir_por_plazo(uow, round_id, equipo_a[0])

        assert [m[1] for m in vista.matchups] == [
            [equipo_b[-1].value],
            [equipo_b[0].value],
        ]

    async def test_el_handicap_propio_de_la_inscripcion_manda_sobre_el_del_perfil(self):
        """La misma regla que usa el reparto automático, en un solo sitio."""
        uow, comp_id, round_id, equipo_a, equipo_b = await _montar()
        for jugador in equipo_b:
            await _dar_handicap_de_usuario(uow, jugador, Decimal("10"))
        await _dar_handicap_propio(uow, comp_id, equipo_b[-1], Decimal("1"))
        await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        vista = await _abrir_por_plazo(uow, round_id, equipo_a[0])

        assert vista.matchups[0][1] == [equipo_b[-1].value]


class TestCuandoFaltanLosEquipos:
    async def test_sin_equipos_repartidos_se_dice_eso_y_no_otra_cosa(self):
        """Antes salía «hay jugadores que no son de este equipo», que despista."""
        uow, _, round_id, equipo_a, _ = await _montar(con_equipos=False)

        with pytest.raises(TeamsNotAssignedError):
            await _entregar(uow).execute(round_id.value, equipo_a[0], [[str(equipo_a[0].value)]])

    async def test_y_tampoco_se_abren(self):
        """Sin equipos no hay sobres que entregar, así que el motivo es ese."""
        uow, _, round_id, equipo_a, _ = await _montar(con_equipos=False)

        with pytest.raises(RivalEnvelopeMissingError):
            await RevealEnvelopesUseCase(uow, _RepoUsuarios(), _Zona()).execute(
                round_id.value, equipo_a[0]
            )

    async def test_y_sin_plazo_el_organizador_se_lleva_el_motivo_de_verdad(self):
        """Ahí sí llega a intentarlo, y entonces el diagnóstico es el bueno.

        «Hay jugadores que no son de este equipo» mandaba a buscar el fallo
        donde no está.
        """
        uow, _, round_id, equipo_a, _ = await _montar(con_equipos=False)

        with pytest.raises(TeamsNotAssignedError):
            await RevealEnvelopesUseCase(uow, _RepoUsuarios(), _Zona(None)).execute(
                round_id.value, equipo_a[0]
            )

    async def test_un_sobre_vacio_no_es_una_entrega(self):
        """Un 200 sin guardar nada deja al capitán creyendo que entregó."""
        uow, _, round_id, equipo_a, _ = await _montar()

        with pytest.raises(EmptyEnvelopeError):
            await _entregar(uow).execute(round_id.value, equipo_a[0], [])


class TestLosNombresQueSeVen:
    async def test_el_capitan_recibe_a_los_suyos_con_nombre_y_handicap(self):
        """Es lo único con lo que ordena, y de los UUID no sale ningún nombre.

        Sin esto la pantalla tendría que pedir aparte las inscripciones —una
        llamada más y otra ronda de permisos— para pintar su propia lista.
        """
        uow, _, round_id, equipo_a, _ = await _montar()
        for jugador in equipo_a:
            await _dar_handicap_de_usuario(uow, jugador, Decimal("12"))

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[0])

        assert {j.user_id for j in vista.my_players} == {uid.value for uid in equipo_a}
        assert all(j.name and j.handicap is not None for j in vista.my_players)

    async def test_quien_no_capitanea_no_recibe_ninguna_lista(self):
        """No tiene sobre que rellenar: los nombres no le hacen falta."""
        uow, _, round_id, equipo_a, _ = await _montar()

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[1])

        assert vista.my_players == []

    async def test_abiertos_los_enfrentamientos_llevan_los_nombres(self):
        """Quien los mira no tiene de dónde sacarlos: vería dos columnas de UUID."""
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )
        await RevealEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[0])

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[1])

        assert vista.player_names[str(equipo_a[1].value)]
        assert vista.player_names[str(equipo_b[0].value)]


class TestElRevelado6HorasAntes:
    async def test_llegada_la_hora_se_abren_solos_al_mirarlos(self):
        """Como la anotación, que se abre sola al llegar el primer golpe: no hay
        proceso de fondo mirando el reloj, lo resuelve quien mira."""
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )
        # La sesión es de mañana (06:00), así que sus sobres se abren a las
        # 00:00 de ese mismo día. Con huso explícito: una hora «pelada» se lee
        # como UTC y en Madrid serían otras
        reloj = _Reloj(datetime(2026, 6, 1, 0, 30, tzinfo=ZoneInfo("Europe/Madrid")))

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios(), reloj, _Zona()).execute(
            round_id.value, equipo_a[1]
        )

        assert vista.revealed is True
        assert len(vista.matchups) == 2

    async def test_antes_de_esa_hora_siguen_cerrados(self):
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )
        reloj = _Reloj(datetime(2026, 5, 31, 23, 0, tzinfo=ZoneInfo("Europe/Madrid")))

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios(), reloj, _Zona()).execute(
            round_id.value, equipo_a[1]
        )

        assert vista.revealed is False
        assert vista.matchups == []

    async def test_la_vista_dice_a_que_hora_se_abren(self):
        """Es el plazo para entregar, así que la pantalla tiene que poder decirlo."""
        uow, _, round_id, equipo_a, _ = await _montar()
        reloj = _Reloj(datetime(2026, 5, 30, 12, 0, tzinfo=ZoneInfo("Europe/Madrid")))

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios(), reloj, _Zona()).execute(
            round_id.value, equipo_a[0]
        )

        assert vista.reveal_scheduled_at is not None
        assert vista.reveal_scheduled_at.hour == 0
        assert vista.reveal_scheduled_at.date() == date(2026, 6, 1)

    async def test_sin_zona_horaria_no_se_abren_solos(self):
        """Sin campo todavía no hay reloj: los abre el organizador a mano."""
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )
        reloj = _Reloj(datetime(2030, 1, 1, 12, 0, tzinfo=ZoneInfo("Europe/Madrid")))

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios(), reloj, _Zona(None)).execute(
            round_id.value, equipo_a[1]
        )

        assert vista.revealed is False
        assert vista.reveal_scheduled_at is None


class TestAbrirlosSinEsperarALaHora:
    async def test_si_los_dos_lo_piden_se_abren_al_entregar_el_segundo(self):
        """Decidido el 23 sep: el que entrega segundo dispara la apertura."""
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value,
                capitan,
                [[str(equipo[1].value)], [str(equipo[0].value)]],
                sin_esperar=True,
            )

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[1])

        assert vista.revealed is True
        assert len(vista.matchups) == 2

    async def test_con_uno_solo_pidiendolo_se_espera(self):
        """El otro capitán tiene derecho a su plazo."""
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        await _entregar(uow).execute(
            round_id.value,
            equipo_a[0],
            [[str(equipo_a[1].value)], [str(equipo_a[0].value)]],
            sin_esperar=True,
        )
        await _entregar(uow).execute(
            round_id.value, equipo_b[0], [[str(equipo_b[1].value)], [str(equipo_b[0].value)]]
        )

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[1])

        assert vista.revealed is False

    async def test_y_la_vista_cuenta_lo_que_ha_pedido_cada_uno(self):
        """La pantalla tiene que poder decir «solo falta que lo marque el otro»."""
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow).execute(
            round_id.value,
            equipo_a[0],
            [[str(equipo_a[1].value)], [str(equipo_a[0].value)]],
            sin_esperar=True,
        )

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[0])

        assert vista.mine.reveal_when_both_ready is True
        assert vista.rival_wants_early is False

    async def test_el_rellenado_automatico_no_cuenta_como_que_lo_pide(self):
        """Ese capitán no entregó nada: no ha pedido adelantar nada.

        Se abre de verdad —con el organizador, que puede con un solo sobre—
        para que el rellenado se EJECUTE: comprobando solo que no se abriera,
        el test pasaba aunque `fill` dejara la marca puesta.
        """
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow).execute(
            round_id.value,
            equipo_a[0],
            [[str(equipo_a[1].value)], [str(equipo_a[0].value)]],
            sin_esperar=True,
        )

        await _abrir_por_plazo(uow, round_id, equipo_a[0])

        async with uow:
            sobres = {s.team: s for s in await uow.envelopes.find_by_round(round_id)}
        assert sobres["B"].automatic is True
        assert sobres["B"].reveal_when_both_ready is False


class TestLoQueElReveladoAutomaticoNoDebeHacer:
    async def test_no_fabrica_sobres_en_una_sesion_que_ya_tiene_partidos(self):
        """Serían unos enfrentamientos inventados que no son los partidos reales.

        El camino manual ya lo impedía; el automático no, y cualquiera que
        abriera la pantalla pasada la hora los creaba.
        """
        uow, _, round_id, equipo_a, _ = await _montar()
        await _marcar_partidos_generados(uow, round_id)
        reloj = _Reloj(datetime(2030, 1, 1, 12, 0, tzinfo=ZoneInfo("Europe/Madrid")))

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios(), reloj, _Zona()).execute(
            round_id.value, equipo_a[0]
        )

        assert vista.revealed is False
        async with uow:
            assert await uow.envelopes.find_by_round(round_id) == []

    async def test_un_equipo_impar_en_parejas_no_tumba_la_pantalla(self):
        """La aplicación no puede rellenar ese sobre, pero eso no es motivo
        para dejar a nadie sin ver la suya.

        Antes el fallo del relleno subía como un 400 para todo el mundo, y el
        capitán que sí entregó se quedaba sin ver ni su sobre ni el plazo.
        """
        uow, _, round_id, equipo_a, _ = await _montar(formato=MatchFormat.FOURBALL, jugadores=6)
        reloj = _Reloj(datetime(2030, 1, 1, 12, 0, tzinfo=ZoneInfo("Europe/Madrid")))

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios(), reloj, _Zona()).execute(
            round_id.value, equipo_a[0]
        )

        assert vista.revealed is False
        assert len(vista.my_players) == 3

    async def test_si_un_sobre_no_se_puede_rellenar_el_otro_no_queda_abierto(self):
        """O la sesión se queda en un estado del que no se sale.

        Abrir A y fallar al rellenar B dejaba A revelado y B cerrado: el
        organizador ya no podía abrirlos —el suyo «ya estaba abierto»— y el
        capitán A tampoco podía corregir su lista. Y el disparador es normal:
        el draft admite equipos desiguales por uno, y en parejas eso significa
        que uno de los dos no se puede rellenar.
        """
        # Siete jugadores: un equipo de cuatro (que sí se puede emparejar) y
        # otro de tres, que es justo lo que deja el draft con impares
        uow, _, round_id, equipo_a, equipo_b = await _montar(
            formato=MatchFormat.FOURBALL, jugadores=7
        )
        par, impar = (equipo_a, equipo_b) if len(equipo_a) % 2 == 0 else (equipo_b, equipo_a)
        assert len(impar) % 2 != 0
        await _entregar(uow).execute(
            round_id.value,
            par[0],
            [[str(par[0].value), str(par[1].value)], [str(par[2].value), str(par[3].value)]],
        )
        reloj = _Reloj(datetime(2030, 1, 1, 12, 0, tzinfo=ZoneInfo("Europe/Madrid")))

        await GetEnvelopesUseCase(uow, _RepoUsuarios(), reloj, _Zona()).execute(
            round_id.value, par[0]
        )

        async with uow:
            sobres = {s.team: s for s in await uow.envelopes.find_by_round(round_id)}
        entregado = sobres["A" if par is equipo_a else "B"]
        assert entregado.is_sealed() is True, "ese sobre no puede quedarse abierto él solo"
        # Y por tanto el capitán puede seguir corrigiendo
        await _entregar(uow).execute(
            round_id.value,
            par[0],
            [[str(par[1].value), str(par[0].value)], [str(par[2].value), str(par[3].value)]],
        )

    async def test_la_sesion_anterior_sin_partidos_todavia_no_ha_acabado(self):
        """«Cero partidos pendientes» no es lo mismo que «ya se jugó».

        Con una sesión anterior aún sin generar, los sobres de esta se abrían
        igual: justo lo que la espera quiere evitar.
        """
        uow, comp_id, round_id, equipo_a, equipo_b = await _montar()
        await _crear_sesion_anterior(uow, comp_id)
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )
        reloj = _Reloj(datetime(2026, 6, 1, 5, 0, tzinfo=ZoneInfo("Europe/Madrid")))

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios(), reloj, _Zona()).execute(
            round_id.value, equipo_a[1]
        )

        assert vista.revealed is False


class TestQuienPuedeAbrirlos:
    async def test_ni_el_organizador_puede_si_falta_un_sobre(self):
        """Abrir desvela el orden de juego: con uno fuera no hay nada que ver.

        Y lo dice la vista, no el cliente: repetir la regla en la pantalla es
        justo donde se desincronizan.
        """
        uow, _, round_id, equipo_a, _ = await _montar()
        organizador = equipo_a[0]
        await _entregar(uow).execute(
            round_id.value, organizador, [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios(), _Reloj(_ANTES), _Zona()).execute(
            round_id.value, organizador
        )

        assert vista.can_reveal is False

    async def test_un_capitan_no_puede_mientras_falte_el_del_rival(self):
        uow, _, round_id, _, equipo_b = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_b[0], [[str(equipo_b[1].value)], [str(equipo_b[0].value)]]
        )

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_b[0])

        assert vista.can_reveal is False

    async def test_y_si_puede_cuando_estan_los_dos(self):
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_b[0])

        assert vista.can_reveal is True

    async def test_quien_solo_mira_nunca_puede(self):
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[1])

        assert vista.can_reveal is False

    async def test_y_abiertos_ya_no_hay_nada_que_abrir(self):
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )
        await RevealEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[0])

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[0])

        assert vista.can_reveal is False


class TestCuandoNoHayPlazoQueVencer:
    """El campo sin zona horaria: 2 de los 805 que hay cargados.

    Sin zona no hay hora que calcular, así que los sobres NO se abren solos
    nunca. Si además nadie pudiera abrirlos a mano, esa sesión se quedaría
    atascada para siempre: su capitán entregó, el sobre está cerrado y
    «generar partidos» lo rechaza mientras haya sobres sin abrir.

    Por eso el organizador conserva ahí la llave —es la salida que ya estaba
    decidida antes del 23 sep—, y solo ahí.
    """

    async def test_el_organizador_puede_abrir_con_un_sobre_fuera(self):
        uow, _, round_id, equipo_a, _ = await _montar()
        organizador = equipo_a[0]
        await _entregar(uow).execute(
            round_id.value, organizador, [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        vista = await GetEnvelopesUseCase(
            uow, _RepoUsuarios(), _Reloj(_ANTES), _Zona(None)
        ).execute(round_id.value, organizador)

        assert vista.reveal_scheduled_at is None
        assert vista.can_reveal is True

    async def test_y_al_abrirlos_la_aplicacion_rellena_el_que_falta(self):
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        organizador = equipo_a[0]
        await _entregar(uow).execute(
            round_id.value, organizador, [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        abierto = await RevealEnvelopesUseCase(uow, _RepoUsuarios(), _Zona(None)).execute(
            round_id.value, organizador
        )

        assert abierto.filled_automatically == ["B"]
        assert len(abierto.matchups) == len(equipo_b)

    async def test_pero_un_capitan_sigue_sin_poder(self):
        """La llave es del que arbitra: el rival no la tiene ni aquí."""
        uow, _, round_id, _, equipo_b = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_b[0], [[str(equipo_b[1].value)], [str(equipo_b[0].value)]]
        )

        vista = await GetEnvelopesUseCase(
            uow, _RepoUsuarios(), _Reloj(_ANTES), _Zona(None)
        ).execute(round_id.value, equipo_b[0])

        assert vista.can_reveal is False
        with pytest.raises(RivalEnvelopeMissingError):
            await RevealEnvelopesUseCase(uow, _RepoUsuarios(), _Zona(None)).execute(
                round_id.value, equipo_b[0]
            )

    async def test_con_zona_el_organizador_no_la_tiene(self):
        """La misma sesión con un campo normal: a esperar como todo el mundo."""
        uow, _, round_id, equipo_a, _ = await _montar()
        organizador = equipo_a[0]
        await _entregar(uow).execute(
            round_id.value, organizador, [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        with pytest.raises(RivalEnvelopeMissingError):
            await RevealEnvelopesUseCase(uow, _RepoUsuarios(), _Zona()).execute(
                round_id.value, organizador
            )

    async def test_manda_el_campo_de_la_sesion_y_no_el_primero(self):
        """Una competición de varios campos: cada sesión va donde se juega.

        Con el primero sin zona, una sesión que sí la tiene conserva su plazo y
        nadie consigue llave por la puerta de atrás.
        """
        uow, _, round_id, equipo_a, _ = await _montar()
        organizador = equipo_a[0]
        await _entregar(uow).execute(
            round_id.value, organizador, [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )
        zona = _Zona(None, de_la_sesion="Europe/Madrid")

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios(), _Reloj(_ANTES), zona).execute(
            round_id.value, organizador
        )

        assert vista.reveal_scheduled_at is not None
        assert vista.can_reveal is False

    async def test_y_al_reves_la_sesion_sin_zona_conserva_su_salida(self):
        """El primero con zona no le quita la salida a la sesión que no la tiene."""
        uow, _, round_id, equipo_a, _ = await _montar()
        organizador = equipo_a[0]
        await _entregar(uow).execute(
            round_id.value, organizador, [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )
        zona = _Zona("Europe/Madrid", de_la_sesion=None)

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios(), _Reloj(_ANTES), zona).execute(
            round_id.value, organizador
        )

        assert vista.reveal_scheduled_at is None
        assert vista.can_reveal is True

class TestLaVistaDiceComoSeRellena:
    """La pantalla no puede saber sola si esa sesión va de uno en uno.

    Que el front repita «estos formatos son de parejas» es duplicar una regla
    que ya vive en el agregado, y es donde se desincronizan.
    """

    async def test_en_individuales_va_uno_por_fila(self):
        uow, _, round_id, equipo_a, _ = await _montar()

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(
            round_id.value, equipo_a[0]
        )

        assert vista.players_per_row == 1

    async def test_y_en_parejas_van_dos(self):
        uow, _, round_id, equipo_a, _ = await _montar(formato=MatchFormat.FOURBALL)

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(
            round_id.value, equipo_a[0]
        )

        assert vista.players_per_row == 2


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

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[0])

        assert vista.mine is not None
        assert vista.mine.entries == [[equipo_a[1].value], [equipo_a[0].value]]
        assert vista.rival_submitted is True
        assert vista.rival is None

    async def test_un_ajeno_a_la_competicion_no_ve_nada(self):
        """Probando identificadores se podía leer la sesión de cualquiera."""
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        with pytest.raises(NotCompetitionParticipantError):
            await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, UserId(uuid4()))

    async def test_un_retirado_tampoco_los_ve(self):
        """Estar inscrito no basta: hay que estarlo APROBADO.

        Una inscripción rechazada o retirada seguía valiendo de llave, y con
        ella se leía quién ha entregado y, abiertos, los enfrentamientos.
        """
        uow, comp_id, round_id, _, _ = await _montar()
        retirado = UserId(uuid4())
        async with uow:
            inscripcion = Enrollment.direct_enroll(
                id=EnrollmentId.generate(), competition_id=comp_id, user_id=retirado
            )
            inscripcion.withdraw()
            await uow.enrollments.add(inscripcion)
            await uow.commit()

        with pytest.raises(NotCompetitionParticipantError):
            await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, retirado)

    async def test_lo_que_relleno_la_aplicacion_se_distingue_de_una_entrega(self):
        """Si no, la pantalla dice que los dos capitanes entregaron y es falso."""
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )
        vista = await _abrir_por_plazo(uow, round_id, equipo_a[1])

        assert vista.team_a_automatic is False
        assert vista.team_b_automatic is True

    async def test_un_espectador_solo_sabe_si_estan_entregados(self):
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[1])

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

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[0])

        assert vista.revealed is False
        assert vista.matchups == []
        assert vista.rival is None

    async def test_abiertos_los_ve_todo_el_mundo(self):
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )
        await RevealEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[0])

        vista = await GetEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[1])

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

        resultado = await RevealEnvelopesUseCase(uow, _RepoUsuarios()).execute(
            round_id.value, equipo_a[0]
        )

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

        vista = await _abrir_por_plazo(uow, round_id, equipo_a[0])

        assert len(vista.matchups) == 2
        assert vista.team_b_automatic is True

    async def test_y_no_pisa_al_que_si_entrego(self):
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
        )

        vista = await _abrir_por_plazo(uow, round_id, equipo_a[0])

        assert [m[0] for m in vista.matchups] == [
            [equipo_a[1].value],
            [equipo_a[0].value],
        ]

    async def test_un_capitan_no_los_abre_si_el_otro_no_ha_entregado(self):
        """Si no, el que entrega primero se lleva la partida.

        El sobre que rellena la aplicación sale en un orden PREDECIBLE —por
        hándicap—, así que un capitán podría entregar, abrir antes de tiempo y
        armar su lista para ganar todos los cruces. El azar de esto está en no
        saber qué hizo el rival. El capitán B, que no organiza, es el caso puro.
        """
        uow, _, round_id, _, equipo_b = await _montar()
        await _entregar(uow).execute(
            round_id.value, equipo_b[0], [[str(equipo_b[1].value)], [str(equipo_b[0].value)]]
        )

        with pytest.raises(RivalEnvelopeMissingError):
            await RevealEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_b[0])

    async def test_con_los_dos_entregados_si_los_abre(self):
        """Ahí ya no hay nada que forzar: las dos listas están hechas."""
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )

        resultado = await RevealEnvelopesUseCase(uow, _RepoUsuarios()).execute(
            round_id.value, equipo_b[0]
        )

        assert len(resultado.matchups) == 2

    async def test_ni_el_organizador_los_abre_con_uno_solo(self):
        """Abrir es lo que desvela el orden de juego, así que con un sobre fuera
        no hay nada que desvelar (decidido el 23 sep).

        El capitán que no aparece no deja nada atascado: al vencer el plazo se
        abren solos y la aplicación rellena lo que falte. Nadie tiene que
        forzarlo a mano.
        """
        uow, _, round_id, equipo_a, _ = await _montar()
        organizador = equipo_a[0]
        await _entregar(uow).execute(
            round_id.value,
            organizador,
            [[str(equipo_a[1].value)], [str(equipo_a[0].value)]],
        )

        with pytest.raises(RivalEnvelopeMissingError):
            await RevealEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, organizador)

    async def test_ni_un_administrador(self):
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow).execute(
            round_id.value,
            equipo_a[0],
            [[str(equipo_a[1].value)], [str(equipo_a[0].value)]],
        )

        with pytest.raises(RivalEnvelopeMissingError):
            await RevealEnvelopesUseCase(uow, _RepoUsuarios()).execute(
                round_id.value, UserId(uuid4()), is_admin=True
            )

    async def test_los_abre_el_organizador_o_un_capitan_y_nadie_mas(self):
        uow, _, round_id, equipo_a, _ = await _montar()

        with pytest.raises(NotCompetitionCreatorError):
            await RevealEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[1])

    async def test_no_se_abren_dos_veces(self):
        uow, _, round_id, equipo_a, _ = await _montar()
        await _abrir_por_plazo(uow, round_id, equipo_a[0])

        with pytest.raises(EnvelopeAlreadyRevealedError):
            await RevealEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[0])

    async def test_sin_equipos_repartidos_no_hay_sobres(self):
        uow = InMemoryUnitOfWork()
        creator_id = UserId(uuid4())
        creada = await create_competition(uow, creator_id)
        await set_competition_status(uow, creada.id, "CLOSED")

        with pytest.raises(RoundNotFoundError):
            await RevealEnvelopesUseCase(uow, _RepoUsuarios()).execute(uuid4(), creator_id)


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
        await RevealEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[0])

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


class TestConLosPartidosYaGenerados:
    async def test_no_se_entrega_un_sobre_para_una_sesion_ya_montada(self):
        """Los partidos ya están hechos: el sobre no cambiaría nada y mentiría.

        Antes se guardaba tan tranquilo, y la sesión quedaba con unos partidos
        que no salían de ningún sobre y unos sobres que no eran de esos
        partidos.
        """
        uow, _, round_id, equipo_a, _ = await _montar()
        await _marcar_partidos_generados(uow, round_id)

        with pytest.raises(RoundAlreadyScheduledError):
            await _entregar(uow).execute(
                round_id.value, equipo_a[0], [[str(equipo_a[1].value)], [str(equipo_a[0].value)]]
            )

    async def test_ni_se_abren(self):
        uow, _, round_id, equipo_a, _ = await _montar()
        await _marcar_partidos_generados(uow, round_id)

        with pytest.raises(RoundAlreadyScheduledError):
            await RevealEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[0])


class TestCuandoCambiaElFormatoDeLaSesion:
    async def test_los_sobres_de_otro_formato_se_tiran(self):
        """Un sobre de parejas no vale para unos individuales.

        El sobre guarda el formato con el que se entregó: si la sesión cambia,
        el capitán ya no puede ni corregirlo —le sigue exigiendo parejas— y al
        generar los partidos se descartaba en silencio al compañero de cada
        fila, con media plantilla sin jugar.
        """
        uow, comp_id, round_id, equipo_a, _ = await _montar(formato=MatchFormat.FOURBALL)
        await _entregar(uow).execute(
            round_id.value,
            equipo_a[0],
            [[str(equipo_a[0].value), str(equipo_a[1].value)]],
        )

        await _cambiar_formato(uow, comp_id, round_id, equipo_a[0], "SINGLES")

        async with uow:
            assert await uow.envelopes.find_by_round(round_id) == []

    async def test_y_si_el_formato_no_cambia_siguen_donde_estaban(self):
        uow, comp_id, round_id, equipo_a, _ = await _montar(formato=MatchFormat.FOURBALL)
        await _entregar(uow).execute(
            round_id.value,
            equipo_a[0],
            [[str(equipo_a[0].value), str(equipo_a[1].value)]],
        )

        await _cambiar_formato(uow, comp_id, round_id, equipo_a[0], "FOURBALL")

        async with uow:
            assert len(await uow.envelopes.find_by_round(round_id)) == 1


class TestElOrganizadorNoPisaLosSobres:
    async def test_sin_sobres_manda_lo_que_diga_el_organizador(self):
        """La sesión que no usa sobres se genera como siempre."""
        uow, _, round_id, _, _ = await _montar()
        a_mano = [object()]

        async with uow:
            assert await EnvelopePairings.decidir(uow, round_id, a_mano) is a_mano

    async def test_con_los_sobres_abiertos_no_valen_emparejamientos_a_mano(self):
        """Serían los sobres por la otra puerta: la guarda se esquivaba así."""
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
            await _entregar(uow).execute(
                round_id.value, capitan, [[str(equipo[1].value)], [str(equipo[0].value)]]
            )
        await RevealEnvelopesUseCase(uow, _RepoUsuarios()).execute(round_id.value, equipo_a[0])

        async with uow:
            with pytest.raises(EnvelopesDecideThePairingsError):
                await EnvelopePairings.decidir(uow, round_id, manual_pairings=[object()])
