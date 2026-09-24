"""
La sala de draft, por fuera (FE #653).

El agregado ya sabe elegir y alternar turnos; aquí se comprueba lo que la sala
necesita del resto: quién puede abrirla, a quién se ofrece, qué pasa cuando se
agota un minuto y qué queda cuando termina.

Las decisiones del 22 sep que fijan esta tabla:

- **El sorteo lo lanza el organizador**, aunque falte un capitán por entrar.
- **El turno agotado lo resuelve quien mire la sala**, como la anotación se abre
  sola al llegar el primer golpe (BE #305): no hay ningún proceso de fondo, y
  dos móviles contando su minuto acabarían eligiendo dos veces.
- **Al terminar, los equipos son los del draft**: quedan guardados como el
  reparto de la competición, que es lo que leen las rondas y los partidos.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.application.exceptions import (
    CompetitionNotClosedError,
    CompetitionNotFoundError,
    InsufficientPlayersError,
    NotCompetitionCreatorError,
    NotCompetitionParticipantError,
)
from src.modules.competition.application.use_cases.get_draft_use_case import GetDraftUseCase
from src.modules.competition.application.use_cases.make_draft_pick_use_case import (
    MakeDraftPickUseCase,
)
from src.modules.competition.application.use_cases.start_draft_use_case import (
    DraftAlreadyStartedError,
    StartDraftUseCase,
)
from src.modules.competition.domain.entities.competition import CaptainMissingError
from src.modules.competition.domain.entities.draft import (
    DraftNotRunningError,
    NotYourTurnError,
    PlayerAlreadyPickedError,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.draft_status import DraftStatus
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


# La hora en la que arrancan todas las salas de esta tabla
AHORA = datetime(2030, 6, 1, 10, 0, 0)


class _Usuario:
    """Lo justo que la sala pide de un usuario: su identificador y su nombre."""

    def __init__(self, user_id: UserId, nombre: str):
        self.id = user_id
        self._nombre = nombre

    def display_name_or_legal(self, nombre_legal: bool) -> str:
        return self._nombre


class _RepoUsuarios:
    """Un repositorio de usuarios con los que se inscribieron."""

    def __init__(self, usuarios: dict[UserId, str]):
        self._usuarios = {uid: _Usuario(uid, nombre) for uid, nombre in usuarios.items()}

    async def find_by_ids(self, user_ids):
        return [self._usuarios[uid] for uid in user_ids if uid in self._usuarios]

    async def find_by_id(self, user_id):
        return self._usuarios.get(user_id)


class _Reloj:
    """El reloj del servidor, que en los tests se mueve a mano."""

    def __init__(self, inicio):
        self.ahora = inicio

    def __call__(self):
        return self.ahora

    def avanza(self, segundos):
        self.ahora = self.ahora + timedelta(seconds=segundos)


async def _montar(jugadores: int = 6, cerrar: bool = True, capitanes: bool = True):
    """Una competición cerrada con `jugadores` inscritos y sus dos capitanes.

    El creador cuenta como uno: crearla ya lo inscribe. Cada uno lleva un
    hándicap distinto —y a propósito NO en orden— para que «el más bajo» sea
    una afirmación de verdad y no el primero de la lista.
    """
    uow = InMemoryUnitOfWork()
    creator_id = UserId(uuid4())
    creada = await create_competition(uow, creator_id)
    resto = [UserId(uuid4()) for _ in range(jugadores - 1)]
    handicaps = [Decimal(h) for h in ("20.0", "4.0", "28.0", "11.0", "36.0", "15.0", "7.0")]
    for jugador, handicap in zip(resto, handicaps, strict=False):
        await create_approved_enrollment(uow, creada.id, jugador, custom_handicap=handicap)
    if cerrar:
        await set_competition_status(uow, creada.id, "CLOSED")
    comp_id = CompetitionId(creada.id)
    if capitanes:
        async with uow:
            competition = await uow.competitions.find_by_id(comp_id)
            competition.name_captains(
                creator_id,
                resto[0],
                approved_player_ids={creator_id, *resto},
                has_teams=False,
            )
            await uow.competitions.update(competition)
            await uow.commit()
    usuarios = _RepoUsuarios(
        {creator_id: "Ana Alba", **{uid: f"Jugador {i}" for i, uid in enumerate(resto, 1)}}
    )
    return uow, comp_id, creator_id, resto, usuarios


def _casos(uow, usuarios):
    """Los tres casos de uso compartiendo el mismo reloj."""
    reloj = _Reloj(AHORA)
    return (
        StartDraftUseCase(uow, usuarios, reloj),
        GetDraftUseCase(uow, usuarios, reloj),
        MakeDraftPickUseCase(uow, usuarios, reloj),
        reloj,
    )


class TestAbrirLaSala:
    async def test_el_organizador_lanza_el_sorteo_y_arranca_el_primer_turno(self):
        """
        Given: una cerrada con sus dos capitanes
        When: el organizador lanza el sorteo
        Then: la sala queda en marcha, con un equipo de turno y su minuto contando
        """
        uow, comp_id, creator_id, _, usuarios = await _montar()
        start, _, _, reloj = _casos(uow, usuarios)

        sala = await start.execute(comp_id.value, creator_id)

        assert sala.status == DraftStatus.IN_PROGRESS.value
        assert sala.current_team in ("A", "B")
        assert sala.first_pick == sala.current_team
        assert sala.turn_started_at == reloj.ahora
        assert sala.seconds_per_turn == 60

    @pytest.mark.parametrize("equipo", ["A", "B"])
    async def test_empieza_el_que_sale_en_el_sorteo(self, equipo):
        """Con el sorteo amañado: el primer turno es el que salió, no uno fijo."""
        uow, comp_id, creator_id, _, usuarios = await _montar()
        start = StartDraftUseCase(uow, usuarios, _Reloj(AHORA), lambda: equipo)

        sala = await start.execute(comp_id.value, creator_id)

        assert sala.first_pick == equipo
        assert sala.current_team == equipo

    async def test_los_capitanes_no_se_eligen_a_si_mismos(self):
        """Nombrarlos ya los fijó en su equipo (BE #320): no entran al draft."""
        uow, comp_id, creator_id, resto, usuarios = await _montar(jugadores=6)
        start, _, _, _ = _casos(uow, usuarios)

        sala = await start.execute(comp_id.value, creator_id)

        elegibles = {j.user_id for j in sala.available_players}
        assert creator_id.value not in elegibles
        assert resto[0].value not in elegibles
        assert len(elegibles) == 4

    async def test_cada_elegible_lleva_su_nombre_y_su_handicap_y_nada_mas(self):
        """Como lo pidió el 22 sep: en la ventana de elegir, nombre y hándicap."""
        uow, comp_id, creator_id, _, usuarios = await _montar()
        start, _, _, _ = _casos(uow, usuarios)

        sala = await start.execute(comp_id.value, creator_id)

        jugador = sala.available_players[0]
        assert set(jugador.model_dump()) == {"user_id", "name", "handicap"}
        assert jugador.name.startswith("Jugador ")
        assert jugador.handicap > 0

    async def test_solo_el_organizador_lo_lanza(self):
        uow, comp_id, _, resto, usuarios = await _montar()
        start, _, _, _ = _casos(uow, usuarios)

        with pytest.raises(NotCompetitionCreatorError):
            await start.execute(comp_id.value, resto[1])

    async def test_un_admin_puede_lanzarlo_en_la_de_otro(self):
        uow, comp_id, _, resto, usuarios = await _montar()
        start, _, _, _ = _casos(uow, usuarios)

        sala = await start.execute(comp_id.value, resto[1], is_admin=True)

        assert sala.status == DraftStatus.IN_PROGRESS.value

    async def test_una_competicion_que_no_existe(self):
        uow, _, creator_id, _, usuarios = await _montar()
        start, _, _, _ = _casos(uow, usuarios)

        with pytest.raises(CompetitionNotFoundError):
            await start.execute(uuid4(), creator_id)

    async def test_con_las_inscripciones_abiertas_no_se_sortea(self):
        """La plantilla todavía puede crecer: el draft sería sobre otra lista."""
        uow, comp_id, creator_id, _, usuarios = await _montar(cerrar=False, capitanes=False)
        start, _, _, _ = _casos(uow, usuarios)

        with pytest.raises(CompetitionNotClosedError):
            await start.execute(comp_id.value, creator_id)

    async def test_sin_capitanes_no_hay_sala(self):
        """El draft ES los capitanes eligiendo: sin ellos no hay quien elija."""
        uow, comp_id, creator_id, _, usuarios = await _montar(capitanes=False)
        start, _, _, _ = _casos(uow, usuarios)

        with pytest.raises(CaptainMissingError):
            await start.execute(comp_id.value, creator_id)

    async def test_sin_nadie_a_quien_elegir_no_se_abre_la_sala(self):
        """Dos inscritos son los dos capitanes: no queda nadie que repartir.

        Abrirla igual dejaba una sala muerta: nadie puede elegir, así que nunca
        termina, y al minuto TODA mirada revienta —la aplicación intenta elegir
        por el capitán y no hay a quién—. Sin forma de salir: ni se reabre ni se
        borra.
        """
        uow, comp_id, creator_id, _, usuarios = await _montar(jugadores=2)
        start, _, _, _ = _casos(uow, usuarios)

        with pytest.raises(InsufficientPlayersError):
            await start.execute(comp_id.value, creator_id)

    async def test_con_un_solo_elegible_si_se_abre(self):
        """Tres inscritos: los dos capitanes y uno más. Equipos de 2 y 1."""
        uow, comp_id, creator_id, _, usuarios = await _montar(jugadores=3)
        start, _, _, _ = _casos(uow, usuarios)

        sala = await start.execute(comp_id.value, creator_id)

        assert len(sala.available_players) == 1

    async def test_no_se_vuelve_a_sortear_con_la_sala_en_marcha(self):
        """Volver a sortear cambiaría el orden con elecciones ya hechas."""
        uow, comp_id, creator_id, _, usuarios = await _montar()
        start, _, _, _ = _casos(uow, usuarios)
        await start.execute(comp_id.value, creator_id)

        with pytest.raises(DraftAlreadyStartedError):
            await start.execute(comp_id.value, creator_id)

    async def test_con_los_equipos_ya_repartidos_tampoco(self):
        """Un draft sobre equipos hechos los reharía por detrás."""
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, _, pick, reloj = _casos(uow, usuarios)
        await start.execute(comp_id.value, creator_id)
        await _completar(uow, comp_id, creator_id, resto, pick, reloj, usuarios)

        with pytest.raises(DraftAlreadyStartedError):
            await start.execute(comp_id.value, creator_id)


class TestLosNombresQueSeVen:
    async def test_cada_eleccion_viaja_con_el_nombre_del_elegido(self):
        """Quien entra a mitad no tiene de dónde sacarlos: sin esto, ve UUIDs."""
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, _, pick, _ = _casos(uow, usuarios)
        sala = await start.execute(comp_id.value, creator_id)
        capitan = creator_id if sala.current_team == "A" else resto[0]
        elegido = sala.available_players[0]

        sala = await pick.execute(comp_id.value, capitan, elegido.user_id)

        assert sala.picks[-1].name == elegido.name

    async def test_y_los_capitanes_llevan_el_suyo(self):
        uow, comp_id, creator_id, _, usuarios = await _montar()
        start, _, _, _ = _casos(uow, usuarios)

        sala = await start.execute(comp_id.value, creator_id)

        assert sala.team_a_captain_name == "Ana Alba"
        assert sala.team_b_captain_name == "Jugador 1"


class TestMirarLaSala:
    async def test_antes_del_sorteo_la_sala_no_existe_todavia(self):
        uow, comp_id, creator_id, _, usuarios = await _montar()
        _, ver, _, _ = _casos(uow, usuarios)

        assert await ver.execute(comp_id.value, creator_id) is None

    async def test_un_ajeno_a_la_competicion_no_la_ve(self):
        """Probando identificadores se sacaban nombres, hándicaps y equipos.

        La sala la ve el grupo, que es la gracia; pero el grupo es el de ESA
        competición, y una privada no se enseña a quien pase por ahí.
        """
        uow, comp_id, creator_id, _, usuarios = await _montar()
        start, ver, _, _ = _casos(uow, usuarios)
        await start.execute(comp_id.value, creator_id)

        with pytest.raises(NotCompetitionParticipantError):
            await ver.execute(comp_id.value, UserId(uuid4()))

    async def test_ni_alguien_que_se_retiro(self):
        """Estar inscrito no basta: hay que estarlo APROBADO.

        Una inscripción retirada o rechazada seguía valiendo de llave, y con
        ella se leían nombres, hándicaps y equipos.
        """
        uow, comp_id, creator_id, _, usuarios = await _montar()
        start, ver, _, _ = _casos(uow, usuarios)
        await start.execute(comp_id.value, creator_id)
        retirado = UserId(uuid4())
        async with uow:
            inscripcion = Enrollment.direct_enroll(
                id=EnrollmentId.generate(), competition_id=comp_id, user_id=retirado
            )
            inscripcion.withdraw()
            await uow.enrollments.add(inscripcion)
            await uow.commit()

        with pytest.raises(NotCompetitionParticipantError):
            await ver.execute(comp_id.value, retirado)

    async def test_cualquier_inscrito_la_ve_en_directo(self):
        """El resto lo mira sin poder tocar: es la ceremonia."""
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, ver, _, _ = _casos(uow, usuarios)
        await start.execute(comp_id.value, creator_id)

        sala = await ver.execute(comp_id.value, resto[-1])

        assert sala.status == DraftStatus.IN_PROGRESS.value
        assert len(sala.available_players) == 4

    async def test_viaja_con_la_hora_del_servidor_para_el_contador(self):
        """El contador del móvil se dibuja contra ESTA hora, no contra la suya.

        Dos móviles con el reloj descuadrado verían minutos distintos, y el que
        fuera adelantado daría el turno por perdido antes de tiempo.
        """
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, ver, _, reloj = _casos(uow, usuarios)
        await start.execute(comp_id.value, creator_id)
        reloj.avanza(20)

        sala = await ver.execute(comp_id.value, resto[-1])

        assert sala.server_time == reloj.ahora
        assert (sala.server_time - sala.turn_started_at).total_seconds() == 20

    async def test_ensena_los_equipos_llenandose(self):
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, ver, pick, _ = _casos(uow, usuarios)
        sala = await start.execute(comp_id.value, creator_id)
        capitan = creator_id if sala.current_team == "A" else resto[0]
        elegido = UserId(sala.available_players[0].user_id)
        await pick.execute(comp_id.value, capitan, elegido.value)

        sala = await ver.execute(comp_id.value, resto[-1])

        equipo = sala.team_a if sala.first_pick == "A" else sala.team_b
        assert elegido.value in equipo
        assert len(sala.available_players) == 3


class TestElegir:
    async def test_el_capitan_de_turno_elige_y_el_turno_salta_al_otro(self):
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, _, pick, reloj = _casos(uow, usuarios)
        sala = await start.execute(comp_id.value, creator_id)
        capitan = creator_id if sala.current_team == "A" else resto[0]
        elegido = UserId(sala.available_players[0].user_id)
        turno = sala.current_team
        reloj.avanza(10)

        sala = await pick.execute(comp_id.value, capitan, elegido.value)

        assert sala.current_team != turno
        # El turno siguiente empezó cuando se acabó el minuto, no cuando alguien
        # miró: si no, el que llega tarde encuentra el reloj parado esperándole
        assert sala.turn_started_at == reloj.ahora
        assert sala.picks[-1].user_id == elegido.value
        assert sala.picks[-1].automatic is False

    async def test_el_capitan_del_otro_equipo_no_elige_en_este_turno(self):
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, _, pick, _ = _casos(uow, usuarios)
        sala = await start.execute(comp_id.value, creator_id)
        el_otro = resto[0] if sala.current_team == "A" else creator_id

        with pytest.raises(NotYourTurnError):
            await pick.execute(comp_id.value, el_otro, sala.available_players[0].user_id)

    async def test_quien_no_capitanea_nada_no_elige(self):
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, _, pick, _ = _casos(uow, usuarios)
        sala = await start.execute(comp_id.value, creator_id)

        with pytest.raises(NotYourTurnError):
            await pick.execute(comp_id.value, resto[-1], sala.available_players[0].user_id)

    async def test_no_se_elige_a_quien_ya_esta_cogido(self):
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, _, pick, _ = _casos(uow, usuarios)
        sala = await start.execute(comp_id.value, creator_id)
        capitan = creator_id if sala.current_team == "A" else resto[0]
        elegido = sala.available_players[0].user_id
        sala = await pick.execute(comp_id.value, capitan, elegido)
        el_otro = resto[0] if capitan == creator_id else creator_id

        with pytest.raises(PlayerAlreadyPickedError):
            await pick.execute(comp_id.value, el_otro, elegido)

    async def test_ni_a_quien_no_esta_inscrito(self):
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, _, pick, _ = _casos(uow, usuarios)
        sala = await start.execute(comp_id.value, creator_id)
        capitan = creator_id if sala.current_team == "A" else resto[0]

        with pytest.raises(PlayerAlreadyPickedError):
            await pick.execute(comp_id.value, capitan, uuid4())

    async def test_sin_sala_abierta_no_se_elige(self):
        uow, comp_id, creator_id, _, usuarios = await _montar()
        _, _, pick, _ = _casos(uow, usuarios)

        with pytest.raises(DraftNotRunningError):
            await pick.execute(comp_id.value, creator_id, uuid4())


class TestElMinutoQueSeAgota:
    async def test_quien_mira_la_sala_resuelve_el_turno_agotado(self):
        """Sin proceso de fondo: lo resuelve la siguiente mirada (BE #305)."""
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, ver, _, reloj = _casos(uow, usuarios)
        sala = await start.execute(comp_id.value, creator_id)
        turno = sala.current_team
        reloj.avanza(61)

        sala = await ver.execute(comp_id.value, resto[-1])

        assert len(sala.picks) == 1
        assert sala.picks[0].automatic is True
        assert sala.picks[0].team == turno
        assert sala.current_team != turno
        # El turno siguiente empezó cuando se acabó el minuto, no cuando alguien
        # miró: si no, el que llega tarde encuentra el reloj parado esperándole
        # El turno siguiente empezó cuando se acabó el minuto, NO cuando alguien
        # miró: si no, el capitán que llega tarde se encuentra el reloj parado
        # esperándole, y una sala que nadie mira resolvería un turno por vistazo
        assert sala.turn_started_at == AHORA + timedelta(seconds=60)

    async def test_la_app_elige_el_handicap_mas_bajo(self):
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, ver, _, reloj = _casos(uow, usuarios)
        sala = await start.execute(comp_id.value, creator_id)
        mas_bajo = min(sala.available_players, key=lambda j: j.handicap).user_id
        reloj.avanza(61)

        sala = await ver.execute(comp_id.value, resto[-1])

        assert sala.picks[0].user_id == mas_bajo

    async def test_varios_minutos_de_nadie_se_resuelven_de_golpe(self):
        """Si nadie entra, la sala no se queda a medias esperando."""
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, ver, _, reloj = _casos(uow, usuarios)
        await start.execute(comp_id.value, creator_id)
        reloj.avanza(61 * 2)

        sala = await ver.execute(comp_id.value, resto[-1])

        assert [p.automatic for p in sala.picks] == [True, True]
        assert len(sala.available_players) == 2

    async def test_al_elegir_tarde_el_turno_ya_no_es_tuyo(self):
        """El capitán que se duerme no elige por encima de lo que hizo la app."""
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, _, pick, reloj = _casos(uow, usuarios)
        sala = await start.execute(comp_id.value, creator_id)
        capitan = creator_id if sala.current_team == "A" else resto[0]
        reloj.avanza(61)

        with pytest.raises(NotYourTurnError):
            await pick.execute(comp_id.value, capitan, sala.available_players[1].user_id)

    async def test_mirar_sin_turno_vencido_no_bloquea_ninguna_fila(self):
        """La sala la refrescan doce móviles cada pocos segundos.

        Bloquear la competición en cada vistazo serializa a todos los
        espectadores sobre la misma fila, y de paso frena cualquier escritura
        de la competición. Solo se bloquea cuando hay un turno que resolver.
        """
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, ver, _, _ = _casos(uow, usuarios)
        await start.execute(comp_id.value, creator_id)
        bloqueos = _contar_bloqueos(uow)

        await ver.execute(comp_id.value, resto[-1])

        assert bloqueos["competitions"] == 0
        assert bloqueos["drafts"] == 0

    async def test_y_con_un_turno_vencido_si_lo_bloquea(self):
        """Resolverlo es escribir: dos miradas a la vez elegirían dos veces."""
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, ver, _, reloj = _casos(uow, usuarios)
        await start.execute(comp_id.value, creator_id)
        reloj.avanza(61)
        bloqueos = _contar_bloqueos(uow)

        await ver.execute(comp_id.value, resto[-1])

        assert bloqueos["drafts"] == 1
        assert bloqueos["competitions"] == 1

    async def test_dentro_del_minuto_no_se_resuelve_nada(self):
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, ver, _, reloj = _casos(uow, usuarios)
        await start.execute(comp_id.value, creator_id)
        reloj.avanza(59)

        sala = await ver.execute(comp_id.value, resto[-1])

        assert sala.picks == []


class TestCuandoTermina:
    async def test_los_equipos_del_draft_quedan_como_el_reparto(self):
        """Es lo que leen las rondas y los partidos: si no, el draft es un adorno."""
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, _, pick, reloj = _casos(uow, usuarios)
        sala = await start.execute(comp_id.value, creator_id)
        sala = await _completar(uow, comp_id, creator_id, resto, pick, reloj, usuarios)

        assert sala.status == DraftStatus.COMPLETED.value
        assert sala.current_team is None
        async with uow:
            reparto = await uow.team_assignments.find_by_competition(comp_id)
        assert reparto is not None
        assert reparto.mode == TeamAssignmentMode.DRAFT
        assert sorted(uid.value for uid in reparto.team_a_player_ids) == sorted(sala.team_a)
        assert sorted(uid.value for uid in reparto.team_b_player_ids) == sorted(sala.team_b)

    async def test_el_ultimo_entra_solo_y_queda_en_el_reparto(self):
        """Al elegir el penúltimo la sala termina: el último no espera su minuto."""
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, _, pick, _ = _casos(uow, usuarios)
        sala = await start.execute(comp_id.value, creator_id)
        for _ in range(3):
            capitan = creator_id if sala.current_team == "A" else resto[0]
            sala = await pick.execute(comp_id.value, capitan, sala.available_players[0].user_id)

        assert sala.status == DraftStatus.COMPLETED.value
        assert sala.available_players == []
        assert [p.automatic for p in sala.picks] == [False, False, False, True]
        async with uow:
            reparto = await uow.team_assignments.find_by_competition(comp_id)
        assert reparto is not None
        elegidos = {*reparto.team_a_player_ids, *reparto.team_b_player_ids}
        assert set(resto[1:]) <= elegidos

    async def test_cada_capitan_encabeza_su_equipo(self):
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, _, pick, reloj = _casos(uow, usuarios)
        await start.execute(comp_id.value, creator_id)

        sala = await _completar(uow, comp_id, creator_id, resto, pick, reloj, usuarios)

        assert sala.team_a[0] == creator_id.value
        assert sala.team_b[0] == resto[0].value

    async def test_terminada_ya_no_se_elige_mas(self):
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, _, pick, reloj = _casos(uow, usuarios)
        await start.execute(comp_id.value, creator_id)
        await _completar(uow, comp_id, creator_id, resto, pick, reloj, usuarios)

        with pytest.raises(DraftNotRunningError):
            await pick.execute(comp_id.value, creator_id, uuid4())

    async def test_y_mirarla_ya_no_resuelve_ningun_turno(self):
        """Sin turno no hay minuto que agotar: la sala se queda como quedó."""
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, ver, pick, reloj = _casos(uow, usuarios)
        await start.execute(comp_id.value, creator_id)
        terminada = await _completar(uow, comp_id, creator_id, resto, pick, reloj, usuarios)
        reloj.avanza(61 * 10)

        sala = await ver.execute(comp_id.value, resto[-1])

        assert [p.user_id for p in sala.picks] == [p.user_id for p in terminada.picks]

    async def test_las_rondas_pasan_a_esperar_partidos(self):
        """Lo mismo que hace el reparto de siempre: si no, la agenda se atasca."""
        uow, comp_id, creator_id, resto, usuarios = await _montar()
        start, _, pick, reloj = _casos(uow, usuarios)
        ronda_id = await _crear_ronda(uow, comp_id)
        await start.execute(comp_id.value, creator_id)

        await _completar(uow, comp_id, creator_id, resto, pick, reloj, usuarios)

        async with uow:
            ronda = await uow.rounds.find_by_id(ronda_id)
        assert ronda.status.value == "PENDING_MATCHES"


def _contar_bloqueos(uow):
    """Cuenta las lecturas con bloqueo que se piden a partir de ahora."""
    cuenta = {"competitions": 0, "drafts": 0}

    def espiar(repo, metodo, clave):
        original = getattr(repo, metodo)

        async def espia(*args, **kwargs):
            cuenta[clave] += 1
            return await original(*args, **kwargs)

        setattr(repo, metodo, espia)

    espiar(uow.competitions, "find_by_id_for_update", "competitions")
    espiar(uow.drafts, "find_by_competition_for_update", "drafts")
    return cuenta


async def _crear_ronda(uow, comp_id):
    """Una ronda esperando equipos, como la deja la agenda."""
    from datetime import date

    from src.modules.competition.domain.entities.round import Round
    from src.modules.competition.domain.value_objects.match_format import MatchFormat
    from src.modules.competition.domain.value_objects.session_type import SessionType
    from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId

    async with uow:
        ronda = Round.create(
            competition_id=comp_id,
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.FOURBALL,
        )
        await uow.rounds.add(ronda)
        await uow.commit()
    return ronda.id


async def _completar(uow, comp_id, creator_id, resto, pick, reloj, usuarios):
    """Elige a todos a mano, cada capitán en su turno, hasta que la sala cierra."""
    from src.modules.competition.application.use_cases.get_draft_use_case import (
        GetDraftUseCase,
    )

    ver = GetDraftUseCase(uow, usuarios, reloj)
    sala = await ver.execute(comp_id.value, creator_id)
    while sala.status == DraftStatus.IN_PROGRESS.value:
        capitan = creator_id if sala.current_team == "A" else resto[0]
        sala = await pick.execute(comp_id.value, capitan, sala.available_players[0].user_id)
    return sala
