"""
Los partidos salen al abrirse los sobres (BE #361).

Con los sobres abiertos los enfrentamientos ya están decididos, así que
«Generar Partidos» no decidía nada: solo copiaba. Y los sobres se abren solos
—6 h antes de la sesión, o en cuanto los dos capitanes lo piden—, de modo que
la sesión podía llegar a su hora con los enfrentamientos a la vista y sin un
solo partido. Decidido el 23 sep: **los partidos se crean al abrirse**.

La condición: **el fallo no puede ser mudo**. Generar necesita datos que
pueden faltar —un jugador sin sexo en su perfil, un color de barras que el
campo no tiene—, y dentro de la lectura que abre los sobres nadie vería el
error. Así que los sobres se quedan abiertos, la sesión sin partidos, y el
motivo **queda apuntado en la sesión**, diciendo a quién le falta qué.

    #    caso                                                   | qué pasa
    -----|------------------------------------------------------|---------------------------------
    P1   abrir a mano, todo en regla                            | partidos = enfrentamientos, SCHEDULED
    P2   abrir porque vence el plazo (al mirar)                 | partidos
    P3   los dos piden no esperar: entrega el segundo           | partidos
    P4   a uno le falta el sexo y el campo solo tiene barras    | abiertos, sin partidos, PENDING_MATCHES,
         por sexo                                               | bloqueo con su nombre y «GENDER»
    P5   a dos les falta                                        | los DOS en el bloqueo, no el primero
    P6   el color de barras no existe en el campo               | «TEE_COLOR» con el color
    P7   la lectura que abre con fallo                          | no revienta y enseña el bloqueo
    P8   fallo inesperado a mitad de escribir                   | abiertos, CERO partidos, «UNEXPECTED»
    P9   reintento a mano tras arreglarlo                       | partidos y bloqueo borrado
    P10  reintento a mano que sigue fallando                    | error con todos los nombres
    P11  rehacer los sobres                                     | el bloqueo se va con ellos
    P12  el calendario                                          | enseña el bloqueo de la sesión
    P13  «mis sesiones sin partidos»                            | las del organizador, no las de otro
    P14  abrir no consulta la RFEG                              | ni una llamada a la red
    P15  torneo ya EN CURSO (sesión del segundo día)            | partidos también
    P16  modo scratch: sin sexo da igual                        | partidos
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    GenerateMatchesRequestDTO,
    GetScheduleRequestDTO,
)
from src.modules.competition.application.services.envelope_desk import EnvelopeDesk
from src.modules.competition.application.use_cases.generate_matches_use_case import (
    GenerateMatchesUseCase,
    PlayersWithoutTeeError,
    TeeColorNotFoundError,
)
from src.modules.competition.application.use_cases.get_envelopes_use_case import (
    GetEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.get_schedule_use_case import (
    GetScheduleUseCase,
)
from src.modules.competition.application.use_cases.list_my_sessions_without_matches_use_case import (
    ListMySessionsWithoutMatchesUseCase,
)
from src.modules.competition.application.use_cases.reset_envelopes_use_case import (
    ResetEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.reveal_envelopes_use_case import (
    RevealEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.submit_envelope_use_case import (
    SubmitEnvelopeUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_generation_block import ENROLLMENT_OPEN
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.setup_mode import SetupMode
from src.modules.competition.domain.value_objects.team_assignment import (
    TeamAssignment as TeamAssignmentVO,
)
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio

# La sesión es del 1 de junio por la mañana: su plazo vence a las 00:00
_PASADO_EL_PLAZO = datetime(2026, 6, 1, 1, 0, tzinfo=ZoneInfo("Europe/Madrid"))


class _Reloj:
    def __init__(self, ahora):
        self._ahora = ahora

    def __call__(self):
        return self._ahora


class _Zona:
    """La zona del campo; `None` es un campo sin zona, cuya sesión no vence."""

    def __init__(self, zona="Europe/Madrid"):
        self._zona = zona

    async def for_competition(self, competition):
        return self._zona

    async def for_course(self, golf_course_id):
        return self._zona


class _Usuario:
    """Lo que la generación y los nombres le piden a un jugador."""

    def __init__(self, user_id, nombre, sexo, handicap=Decimal("12.0")):
        self.id = user_id
        self.nombre = nombre
        self.gender = sexo
        self.handicap = MagicMock(value=float(handicap))
        self.handicap_updated_at = None
        self.country_code = CountryCode("ES")

    def display_name_or_legal(self, nombre_legal: bool) -> str:
        return self.nombre

    def get_full_name(self) -> str:
        return self.nombre


class _Usuarios:
    """El repositorio de usuarios, con el sexo que tenga cada uno."""

    def __init__(self):
        self.por_id: dict = {}

    def poner(self, user_id, nombre, sexo):
        self.por_id[user_id] = _Usuario(user_id, nombre, sexo)

    async def find_by_id(self, user_id):
        return self.por_id.get(user_id)

    async def find_by_ids(self, user_ids):
        return [self.por_id[u] for u in user_ids if u in self.por_id]

    async def save(self, user):
        pass


def _campo(barras):
    """Un campo con esas barras —(color, sexo)— y 18 hoyos."""
    tees = []
    for color, sexo in barras:
        tee = MagicMock()
        tee.color = color
        tee.gender = sexo
        tee.course_rating = Decimal("71.2")
        tee.slope_rating = 128
        tees.append(tee)
    hoyos = []
    for i in range(1, 19):
        hoyo = MagicMock()
        hoyo.number = i
        hoyo.par = 4
        hoyo.stroke_index = i
        hoyos.append(hoyo)
    campo = MagicMock()
    campo.tees = tees
    campo.reference_card = hoyos
    return campo


class _Campos:
    def __init__(self, campo):
        self.campo = campo

    async def find_by_id(self, golf_course_id):
        return self.campo


# Barras de los dos sexos, como Altea: el caso de verdad del 23 sep
_POR_SEXO = [(TeeColor.YELLOW, Gender.MALE), (TeeColor.YELLOW, Gender.FEMALE)]


class _Torneo:
    """Una cerrada con capitanes, equipos de 2 y una sesión de individuales."""

    def __init__(self, uow, comp_id, ronda_id, organizador, equipo_a, equipo_b, usuarios, campos):
        self.uow = uow
        self.comp_id = comp_id
        self.ronda_id = ronda_id
        self.organizador = organizador
        self.equipo_a = equipo_a
        self.equipo_b = equipo_b
        self.usuarios = usuarios
        self.campos = campos
        self.rfeg = AsyncMock()

    def generador(self):
        return GenerateMatchesUseCase(
            uow=self.uow,
            golf_course_repository=self.campos,
            user_repository=self.usuarios,
            handicap_service=self.rfeg,
        )

    def entregar(self):
        return SubmitEnvelopeUseCase(self.uow, self.usuarios, generador=self.generador())

    def mirar(self, reloj=None):
        return GetEnvelopesUseCase(
            self.uow,
            self.usuarios,
            reloj or _Reloj(datetime(2026, 5, 20, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))),
            _Zona(),
            generador=self.generador(),
        )

    def abrir(self):
        """Abre los sobres como en la vida real: vencido el plazo, al mirarlos.

        Abrirlos a mano ya no lo hace nadie con plazo que vencer (BE #374): antes
        de hora solo con el permiso de los dos capitanes.
        """
        mirar = self.mirar(_Reloj(_PASADO_EL_PLAZO))

        class _PorPlazo:
            async def execute(self, round_id, quien):
                return await mirar.execute(round_id, quien)

        return _PorPlazo()

    def abrir_a_mano_sin_plazo(self):
        """La única llave que queda: el organizador, en una sesión que no vence."""
        return RevealEnvelopesUseCase(
            self.uow, self.usuarios, _Zona(None), generador=self.generador()
        )

    async def entregan_los_dos(self, sin_esperar=(False, False)):
        """Cada capitán entrega su orden tal cual está el equipo."""
        entregar = self.entregar()
        await entregar.execute(
            self.ronda_id.value,
            self.equipo_a[0],
            [[str(u.value)] for u in self.equipo_a],
            sin_esperar=sin_esperar[0],
        )
        await entregar.execute(
            self.ronda_id.value,
            self.equipo_b[0],
            [[str(u.value)] for u in self.equipo_b],
            sin_esperar=sin_esperar[1],
        )

    async def ronda(self):
        async with self.uow:
            return await self.uow.rounds.find_by_id(self.ronda_id)

    async def partidos(self):
        async with self.uow:
            return await self.uow.matches.find_by_round(self.ronda_id)


async def _montar(
    barras=None,
    sexos=None,
    modo=PlayMode.HANDICAP,
    color=None,
    estado="CLOSED",
    montaje=SetupMode.RYDER_CUP,
):
    """Monta el torneo. `sexos` es el de cada jugador: A1, A2, B1, B2."""
    uow = InMemoryUnitOfWork()
    organizador = UserId(uuid4())
    jugadores = [organizador, *(UserId(uuid4()) for _ in range(3))]
    equipo_a, equipo_b = jugadores[:2], jugadores[2:]
    usuarios = _Usuarios()
    nombres = ["Ana Uno", "Bea Dos", "Carla Tres", "Dani Cuatro"]
    for uid, nombre, sexo in zip(jugadores, nombres, sexos or [Gender.MALE] * 4, strict=True):
        usuarios.poner(uid, nombre, sexo)

    competicion = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=organizador,
        name=CompetitionName("Ryder de prueba"),
        dates=DateRange(start_date=date(2026, 6, 1), end_date=date(2026, 6, 2)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=modo,
        max_players=24,
        team_assignment=TeamAssignmentVO.MANUAL,
        team_1_name="Europa",
        team_2_name="Estados Unidos",
        setup_mode=montaje,
    )
    if competicion.is_draft():
        competicion.activate()
    competicion.name_captains(
        equipo_a[0], equipo_b[0], approved_player_ids=jugadores, has_teams=False
    )
    if competicion.status.value == "ACTIVE":
        competicion.close_enrollments()
    if estado == "IN_PROGRESS":
        competicion.start()
    if estado == "ACTIVE":
        competicion.reopen_enrollments()
    if estado == "CANCELLED":
        competicion.cancel()

    ronda = Round.create(
        competition_id=competicion.id,
        golf_course_id=GolfCourseId.generate(),
        round_date=date(2026, 6, 1),
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )
    ronda.mark_teams_assigned()

    async with uow:
        await uow.competitions.add(competicion)
        for uid in jugadores:
            await uow.enrollments.add(
                Enrollment(
                    id=EnrollmentId.generate(),
                    competition_id=competicion.id,
                    user_id=uid,
                    status=EnrollmentStatus.APPROVED,
                    tee_color=color,
                )
            )
        await uow.team_assignments.add(
            TeamAssignment.create(
                competition_id=competicion.id,
                mode=TeamAssignmentMode.DRAFT,
                team_a_player_ids=equipo_a,
                team_b_player_ids=equipo_b,
            )
        )
        await uow.rounds.add(ronda)

    return _Torneo(
        uow,
        competicion.id,
        ronda.id,
        organizador,
        equipo_a,
        equipo_b,
        usuarios,
        _Campos(_campo(barras or _POR_SEXO)),
    )


def _parejas(partidos):
    """Quién juega contra quién, en el orden de los partidos."""
    return [
        (p.team_a_players[0].user_id, p.team_b_players[0].user_id)
        for p in sorted(partidos, key=lambda p: p.match_number)
    ]


class TestLosPartidosSalenAlAbrir:
    async def test_p1_abrir_a_mano_crea_los_partidos_de_los_sobres(self):
        """A mano solo abre el organizador en una sesión sin plazo (BE #374)."""
        torneo = await _montar()
        await torneo.entregan_los_dos()

        await torneo.abrir_a_mano_sin_plazo().execute(torneo.ronda_id.value, torneo.organizador)

        partidos = await torneo.partidos()
        assert _parejas(partidos) == [
            (torneo.equipo_a[0], torneo.equipo_b[0]),
            (torneo.equipo_a[1], torneo.equipo_b[1]),
        ]
        ronda = await torneo.ronda()
        assert ronda.status == RoundStatus.SCHEDULED
        assert ronda.match_generation_block is None

    async def test_p2_abrir_al_vencer_el_plazo_tambien(self):
        torneo = await _montar()
        await torneo.entregan_los_dos()

        vista = await torneo.mirar(_Reloj(_PASADO_EL_PLAZO)).execute(
            torneo.ronda_id.value, torneo.organizador
        )

        assert vista.revealed is True
        assert len(await torneo.partidos()) == 2
        assert (await torneo.ronda()).status == RoundStatus.SCHEDULED

    async def test_p3_los_dos_piden_no_esperar_y_la_segunda_entrega_los_crea(self):
        torneo = await _montar()

        await torneo.entregan_los_dos(sin_esperar=(True, True))

        assert len(await torneo.partidos()) == 2
        assert (await torneo.ronda()).status == RoundStatus.SCHEDULED


class TestSiNoSePuedenGenerar:
    async def test_p4_a_uno_le_falta_el_sexo_y_queda_apuntado_con_su_nombre(self):
        torneo = await _montar(sexos=[Gender.MALE, None, Gender.MALE, Gender.FEMALE])
        await torneo.entregan_los_dos()

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        assert await torneo.partidos() == []
        ronda = await torneo.ronda()
        assert ronda.status == RoundStatus.PENDING_MATCHES
        bloqueo = ronda.match_generation_block
        assert bloqueo.reason == "PLAYERS_WITHOUT_TEE"
        assert [(p.user_id, p.name, p.missing) for p in bloqueo.players] == [
            (torneo.equipo_a[1], "Bea Dos", "GENDER")
        ]

    async def test_p4_los_sobres_siguen_abiertos(self):
        torneo = await _montar(sexos=[Gender.MALE, None, Gender.MALE, Gender.MALE])
        await torneo.entregan_los_dos()

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        async with torneo.uow:
            sobres = await torneo.uow.envelopes.find_by_round(torneo.ronda_id)
        assert all(not s.is_sealed() for s in sobres)

    async def test_p5_salen_todos_los_que_faltan_no_solo_el_primero(self):
        torneo = await _montar(sexos=[None, Gender.MALE, Gender.MALE, None])
        await torneo.entregan_los_dos()

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        bloqueo = (await torneo.ronda()).match_generation_block
        assert {p.name for p in bloqueo.players} == {"Ana Uno", "Dani Cuatro"}

    async def test_p6_un_color_que_el_campo_no_tiene(self):
        torneo = await _montar(color=TeeColor.WHITE)
        await torneo.entregan_los_dos()

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        bloqueo = (await torneo.ronda()).match_generation_block
        assert {p.missing for p in bloqueo.players} == {"TEE_COLOR"}
        assert {p.tee_color for p in bloqueo.players} == {"WHITE"}
        assert len(bloqueo.players) == 4

    async def test_p7_la_lectura_que_los_abre_no_revienta_y_lo_cuenta(self):
        torneo = await _montar(sexos=[Gender.MALE, None, Gender.MALE, Gender.MALE])
        await torneo.entregan_los_dos()

        vista = await torneo.mirar(_Reloj(_PASADO_EL_PLAZO)).execute(
            torneo.ronda_id.value, torneo.equipo_b[0]
        )

        assert vista.revealed is True
        assert vista.match_generation_block is not None
        assert vista.match_generation_block.players[0].name == "Bea Dos"

    async def test_p8_un_fallo_a_mitad_no_deja_partidos_a_medias(self):
        torneo = await _montar()
        await torneo.entregan_los_dos()
        # El segundo partido revienta al guardarse: el primero ya estaba dentro
        guardar = torneo.uow.matches.add
        llamadas = []

        async def guardar_y_fallar_al_segundo(partido):
            llamadas.append(partido)
            if len(llamadas) == 2:
                raise RuntimeError("se cae la base de datos")
            await guardar(partido)

        torneo.uow.matches.add = guardar_y_fallar_al_segundo

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        assert await torneo.partidos() == []
        ronda = await torneo.ronda()
        assert ronda.status == RoundStatus.PENDING_MATCHES
        assert ronda.match_generation_block.reason == "UNEXPECTED"
        async with torneo.uow:
            sobres = await torneo.uow.envelopes.find_by_round(torneo.ronda_id)
        assert all(not s.is_sealed() for s in sobres)


class TestElReintento:
    async def test_p9_arreglado_el_perfil_generar_a_mano_los_crea_y_borra_el_bloqueo(self):
        torneo = await _montar(sexos=[Gender.MALE, None, Gender.MALE, Gender.MALE])
        await torneo.entregan_los_dos()
        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)
        torneo.usuarios.poner(torneo.equipo_a[1], "Bea Dos", Gender.FEMALE)

        await torneo.generador().execute(
            GenerateMatchesRequestDTO(round_id=torneo.ronda_id.value), torneo.organizador
        )

        assert len(await torneo.partidos()) == 2
        ronda = await torneo.ronda()
        assert ronda.status == RoundStatus.SCHEDULED
        assert ronda.match_generation_block is None

    async def test_p10_si_sigue_faltando_el_error_nombra_a_todos(self):
        torneo = await _montar(sexos=[None, Gender.MALE, Gender.MALE, None])
        await torneo.entregan_los_dos()
        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        with pytest.raises(PlayersWithoutTeeError) as error:
            await torneo.generador().execute(
                GenerateMatchesRequestDTO(round_id=torneo.ronda_id.value), torneo.organizador
            )

        # Sigue siendo el error de siempre para quien ya lo capturaba
        assert isinstance(error.value, TeeColorNotFoundError)
        mensaje = str(error.value)
        assert "Ana Uno" in mensaje
        assert "Dani Cuatro" in mensaje
        assert "None" not in mensaje

    async def test_p11_rehacer_los_sobres_se_lleva_el_bloqueo(self):
        torneo = await _montar(sexos=[Gender.MALE, None, Gender.MALE, Gender.MALE])
        await torneo.entregan_los_dos()
        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        await ResetEnvelopesUseCase(torneo.uow, torneo.usuarios).execute(
            torneo.ronda_id.value, torneo.organizador
        )

        assert (await torneo.ronda()).match_generation_block is None


class TestDondeSeVe:
    async def test_p12_el_calendario_ensena_el_bloqueo_de_la_sesion(self):
        torneo = await _montar(sexos=[Gender.MALE, None, Gender.MALE, Gender.MALE])
        await torneo.entregan_los_dos()
        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        calendario = await GetScheduleUseCase(torneo.uow).execute(
            GetScheduleRequestDTO(competition_id=torneo.comp_id.value)
        )

        sesion = calendario.days[0].rounds[0]
        assert sesion.match_generation_block.reason == "PLAYERS_WITHOUT_TEE"
        assert sesion.match_generation_block.players[0].name == "Bea Dos"
        assert sesion.match_generation_block.players[0].missing == "GENDER"

    async def test_p13_el_organizador_ve_sus_sesiones_sin_partidos(self):
        torneo = await _montar(sexos=[Gender.MALE, None, Gender.MALE, Gender.MALE])
        await torneo.entregan_los_dos()
        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        mias = await ListMySessionsWithoutMatchesUseCase(torneo.uow).execute(torneo.organizador)
        de_otro = await ListMySessionsWithoutMatchesUseCase(torneo.uow).execute(torneo.equipo_b[0])

        assert [s.round_id for s in mias] == [torneo.ronda_id.value]
        assert mias[0].competition_name == "Ryder De Prueba"
        assert mias[0].reason == "PLAYERS_WITHOUT_TEE"
        assert de_otro == []

    async def test_p13_de_una_cancelada_no_queda_nada_que_arreglar(self):
        torneo = await _montar(sexos=[Gender.MALE, None, Gender.MALE, Gender.MALE])
        await torneo.entregan_los_dos()
        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)
        async with torneo.uow:
            competicion = await torneo.uow.competitions.find_by_id(torneo.comp_id)
            competicion.cancel()
            await torneo.uow.competitions.update(competicion)

        assert (
            await ListMySessionsWithoutMatchesUseCase(torneo.uow).execute(torneo.organizador) == []
        )

    async def test_p13_sin_bloqueo_no_sale_nada(self):
        torneo = await _montar()
        await torneo.entregan_los_dos()
        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        assert (
            await ListMySessionsWithoutMatchesUseCase(torneo.uow).execute(torneo.organizador) == []
        )


class TestCasosDeBorde:
    async def test_p14_abrir_no_consulta_la_rfeg(self):
        torneo = await _montar()
        await torneo.entregan_los_dos()

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        assert len(await torneo.partidos()) == 2
        torneo.rfeg.search_handicap.assert_not_awaited()

    async def test_p15_con_el_torneo_en_curso_tambien(self):
        torneo = await _montar(estado="IN_PROGRESS")
        await torneo.entregan_los_dos()

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        assert len(await torneo.partidos()) == 2

    async def test_p15_y_el_reintento_a_mano_tambien(self):
        torneo = await _montar(
            estado="IN_PROGRESS", sexos=[Gender.MALE, None, Gender.MALE, Gender.MALE]
        )
        await torneo.entregan_los_dos()
        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)
        torneo.usuarios.poner(torneo.equipo_a[1], "Bea Dos", Gender.FEMALE)

        await torneo.generador().execute(
            GenerateMatchesRequestDTO(round_id=torneo.ronda_id.value), torneo.organizador
        )

        assert len(await torneo.partidos()) == 2

    async def test_p16_en_scratch_el_sexo_da_igual(self):
        torneo = await _montar(modo=PlayMode.SCRATCH, sexos=[None] * 4)
        await torneo.entregan_los_dos()

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        assert len(await torneo.partidos()) == 2


class TestElCableado:
    """P17: los proveedores de la API montan los sobres CON el generador.

    Sin él, abrir no crea partidos y no avisa de nada: es la clase de cableado
    incompleto que pierde una regla sin que nadie lo note.
    """

    @pytest.mark.parametrize(
        "proveedor",
        ["get_submit_envelope_use_case", "get_envelopes_use_case", "get_reveal_envelopes_use_case"],
    )
    async def test_p17_los_tres_caminos_que_abren_llevan_el_generador(self, proveedor):
        from src.config import dependencies

        caso = getattr(dependencies, proveedor)(
            uow=MagicMock(), user_uow=MagicMock(), gc_uow=MagicMock(), scoring_service=MagicMock()
        )

        generador = caso._desk._generador
        assert isinstance(generador, GenerateMatchesUseCase)
        # La misma Unit of Work: abrir y crear los partidos van juntos
        assert generador._uow is caso._uow
        # Y sin RFEG: al abrir no se llama a la red
        assert generador._handicap_service is None


class TestLaRevisionLocal:
    """Lo que encontró la revisión antes de subir (R1-R4)."""

    async def test_r1_si_otro_ya_los_creo_no_se_borran_ni_se_rehacen(self):
        """Dos móviles abren a la vez: el segundo llega con la sesión vieja
        en memoria, pero los partidos del primero ya están en la base de datos.
        """
        from src.modules.competition.application.services.envelope_desk import EnvelopeDesk

        torneo = await _montar()
        await torneo.entregan_los_dos()
        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)
        antes = {p.id for p in await torneo.partidos()}
        assert len(antes) == 2

        async with torneo.uow:
            # Lo que el segundo tiene en memoria: la sesión aún sin partidos
            vieja = await torneo.uow.rounds.find_by_id(torneo.ronda_id)
            vieja._status = RoundStatus.PENDING_MATCHES
            competicion = await torneo.uow.competitions.find_by_id(torneo.comp_id)
            desk = EnvelopeDesk(torneo.uow, torneo.usuarios, generador=torneo.generador())

            await desk.generar_los_partidos(vieja, competicion)

        assert {p.id for p in await torneo.partidos()} == antes
        assert (await torneo.ronda()).match_generation_block is None

    async def test_r2_con_genero_pero_sin_barras_de_su_genero_es_el_color(self):
        torneo = await _montar(
            barras=[(TeeColor.YELLOW, Gender.MALE)],
            sexos=[Gender.MALE, Gender.FEMALE, Gender.MALE, Gender.MALE],
        )
        await torneo.entregan_los_dos()

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        [jugadora] = (await torneo.ronda()).match_generation_block.players
        assert jugadora.name == "Bea Dos"
        assert jugadora.missing == "TEE_COLOR"
        assert jugadora.tee_color == "YELLOW"

    async def test_r3_una_sesion_que_no_espera_partidos_no_revienta_la_apertura(self):
        from src.modules.competition.application.services.envelope_desk import EnvelopeDesk

        torneo = await _montar()
        async with torneo.uow:
            sesion = await torneo.uow.rounds.find_by_id(torneo.ronda_id)
            sesion._status = RoundStatus.PENDING_TEAMS
            competicion = await torneo.uow.competitions.find_by_id(torneo.comp_id)
            generador = torneo.generador()
            generador.generar_dentro = AsyncMock(wraps=generador.generar_dentro)
            desk = EnvelopeDesk(torneo.uow, torneo.usuarios, generador=generador)

            await desk.generar_los_partidos(sesion, competicion)

        # Ni se intenta: intentarlo es un error «inesperado» en el registro
        generador.generar_dentro.assert_not_awaited()
        assert (await torneo.ronda()).match_generation_block is None
        assert await torneo.partidos() == []

    async def test_r4_un_retirado_es_falta_de_inscripcion_no_de_genero(self):
        torneo = await _montar(sexos=[Gender.MALE, None, Gender.MALE, Gender.MALE])
        await torneo.entregan_los_dos()
        async with torneo.uow:
            for inscripcion in await torneo.uow.enrollments.find_by_competition(torneo.comp_id):
                if inscripcion.user_id == torneo.equipo_a[1]:
                    inscripcion._status = EnrollmentStatus.WITHDRAWN
                    await torneo.uow.enrollments.update(inscripcion)

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        assert (await torneo.ronda()).match_generation_block.reason == "NOT_ENOUGH_PLAYERS"


class TestLaAgendaTambienLosAbre:
    """Mirar la agenda —la de la ficha o la de «Equipos y partidos»— abre los
    sobres vencidos (BE #367). Si nadie abría la página del sobre, la sesión
    llegaba a su hora con los sobres cerrados y, desde la #361, sin partidos.

        #   caso                                               | al leer la agenda
        ----|--------------------------------------------------|---------------------
        S1  Ryder, entregados y vencido, nadie mira el sobre   | se abren y salen los partidos
        S2  lo mismo sin que nadie entregara                   | se rellenan, se abren y salen
        S3  antes del plazo                                    | nada
        S4  modo manual, vencido                               | nunca abre ni genera
    """

    def _agenda(self, torneo, reloj):
        mesa = EnvelopeDesk(torneo.uow, torneo.usuarios, _Reloj(reloj), _Zona(), torneo.generador())
        return GetScheduleUseCase(torneo.uow, sobres=mesa).execute(
            GetScheduleRequestDTO(competition_id=torneo.comp_id.value)
        )

    async def test_s1_vencido_leer_la_agenda_los_abre_y_salen_los_partidos(self):
        torneo = await _montar()
        await torneo.entregan_los_dos()

        agenda = await self._agenda(torneo, _PASADO_EL_PLAZO)

        assert len(await torneo.partidos()) == 2
        assert agenda.days[0].rounds[0].status == "SCHEDULED"
        assert len(agenda.days[0].rounds[0].matches) == 2

    async def test_s2_sin_que_nadie_entregara_tambien(self):
        torneo = await _montar()

        await self._agenda(torneo, _PASADO_EL_PLAZO)

        assert len(await torneo.partidos()) == 2

    async def test_s3_antes_del_plazo_no_abre_nada(self):
        torneo = await _montar()
        await torneo.entregan_los_dos()

        await self._agenda(torneo, datetime(2026, 5, 20, 12, 0, tzinfo=ZoneInfo("Europe/Madrid")))

        assert await torneo.partidos() == []

    async def test_s5_de_una_cancelada_no_se_abre_nada(self):
        """Revisión de la #367: ya no hay nada que jugar, y ahora mirarla puede
        cualquiera. Abrirlos sería escribir en una competición que se acabó."""
        torneo = await _montar(estado="CANCELLED")
        await torneo.entregan_los_dos()

        await self._agenda(torneo, _PASADO_EL_PLAZO)

        async with torneo.uow:
            sobres = await torneo.uow.envelopes.find_by_round(torneo.ronda_id)
        assert all(sobre.is_sealed() for sobre in sobres)

    async def test_s5b_ni_mirando_la_pagina_del_sobre(self):
        """La regla vive en `revelar_si_toca`: la agenda no es la única puerta."""
        torneo = await _montar(estado="CANCELLED")
        await torneo.entregan_los_dos()

        await torneo.mirar(_Reloj(_PASADO_EL_PLAZO)).execute(
            torneo.ronda_id.value, torneo.organizador
        )

        async with torneo.uow:
            sobres = await torneo.uow.envelopes.find_by_round(torneo.ronda_id)
        assert all(sobre.is_sealed() for sobre in sobres)

    async def test_s4_en_modo_manual_nunca(self):
        torneo = await _montar(montaje=SetupMode.MANUAL)

        await self._agenda(torneo, _PASADO_EL_PLAZO)

        assert await torneo.partidos() == []


class TestConLaCompeticionReabierta:
    """Revisión de la FE #711: los sobres se abren con las inscripciones
    reabiertas. No hay partidos que crear todavía, pero sin un motivo apuntado,
    al volver a cerrarla la sesión se quedaba atascada: en modo Ryder «Generar»
    solo sale como reintento, y los sobres ya estaban abiertos."""

    async def test_abrirse_con_las_inscripciones_abiertas_deja_el_motivo(self):
        torneo = await _montar(estado="ACTIVE")
        await torneo.entregan_los_dos()

        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)

        ronda = await torneo.ronda()
        assert await torneo.partidos() == []
        assert ronda.match_generation_block.reason == ENROLLMENT_OPEN
