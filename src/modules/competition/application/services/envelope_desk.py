"""
EnvelopeDesk - Lo que las tres acciones de los sobres comparten (FE #655).

Entregar, mirar y abrir necesitan lo mismo: la ronda, la competicion a la que
pertenece, y quien es capitan de que equipo.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    InsufficientPlayersError,
    NotCompetitionParticipantError,
    RoundNotFoundError,
)
from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.application.services.team_roster import TeamRoster
from src.modules.competition.application.use_cases.generate_matches_use_case import (
    GenerateMatchesUseCase,
    NoGolfCourseForHandicapError,
    NoTeamAssignmentError,
    PlayersWithoutTeeError,
)
from src.modules.competition.domain.entities.competition import (
    Competition,
    TeamsNotAssignedError,
)
from src.modules.competition.domain.entities.envelope import (
    EN_PAREJAS,
    EmptyEnvelopeError,
    Envelope,
    OddTeamForPairsError,
)
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.envelope_reveal_service import (
    EnvelopeRevealService,
)
from src.modules.competition.domain.services.scoring_opening_service import (
    ScoringOpeningService,
)
from src.modules.competition.domain.value_objects.competition_status import (
    SE_JUEGA,
    CompetitionStatus,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.match_generation_block import (
    ENROLLMENT_OPEN,
    NO_GOLF_COURSE,
    NO_TEAMS,
    NOT_ENOUGH_PLAYERS,
    PLAYERS_WITHOUT_TEE,
    UNEXPECTED,
    MatchGenerationBlock,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)

# A partir de aqui la sesion ya tiene partidos generados
_CON_PARTIDOS_YA_HECHOS = (
    RoundStatus.SCHEDULED,
    RoundStatus.IN_PROGRESS,
    RoundStatus.COMPLETED,
)


# El orden de las sesiones dentro de un dia. Por HORA y no por letra, que
# alfabeticamente la tarde iria antes que la mañana
ORDEN_DE_SESION = {
    SessionType.MORNING: 0,
    SessionType.AFTERNOON: 1,
    SessionType.EVENING: 2,
}
_ORDEN_DE_SESION = ORDEN_DE_SESION


class RoundAlreadyScheduledError(Exception):
    """Esa sesion ya tiene sus partidos generados."""

    pass


class EnvelopeDesk:
    """La mesa donde se reciben y se abren los sobres."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repository: UserRepositoryInterface,
        clock: Callable[[], datetime] | None = None,
        timezone_service: ICompetitionTimezone | None = None,
        generador: GenerateMatchesUseCase | None = None,
    ):
        """
        Args:
            uow: Unit of Work del modulo
            user_repository: De donde sale el handicap de quien no tiene uno
                propio en esta competicion, que es casi todo el mundo
            clock: El reloj del SERVIDOR, para el revelado del plazo. Se
                inyecta para poder moverlo en los tests, nunca para que lo
                ponga el cliente
            timezone_service: La zona del campo donde se juega. Sin ella no
                hay hora que calcular: esos sobres no se abren solos nunca y
                los abre a mano el que arbitra, que es el unico con llave ahi
            generador: Lo que crea los partidos al abrirse los sobres (BE #361),
                sobre la MISMA Unit of Work. Los proveedores de la API lo
                inyectan siempre; sin el, abrir no crea partidos
        """
        self._uow = uow
        self._generador = generador
        self._user_repo = user_repository
        self._clock = clock or (lambda: datetime.now(UTC))
        self._timezone = timezone_service

    @property
    def ahora(self) -> datetime:
        """La hora del servidor, con huso: se compara con horas de campo."""
        momento = self._clock()
        return momento if momento.tzinfo else momento.replace(tzinfo=UTC)

    @property
    def user_repository(self) -> UserRepositoryInterface:
        """De donde salen nombres y handicaps."""
        return self._user_repo

    async def ronda_y_competicion(
        self, round_id: RoundId, bloquear: bool = False
    ) -> tuple[Round, Competition]:
        """La sesion y su competicion, bloqueada cuando se va a escribir.

        Bloquear la competicion serializa las entregas de esa competicion, que
        es justo lo que hace falta: el sobre se crea la primera vez que el
        capitan entrega, y dos peticiones a la vez leerian que no existe, las
        dos lo crearian, y una reventaria contra la clave unica con un 500.

        Raises:
            RoundNotFoundError: Si la ronda no existe
            CompetitionNotFoundError: Si su competicion no existe
        """
        ronda = await self._uow.rounds.find_by_id(round_id)
        if ronda is None:
            raise RoundNotFoundError(f"No existe la ronda {round_id.value}")
        competition = (
            await self._uow.competitions.find_by_id_for_update(ronda.competition_id)
            if bloquear
            else await self._uow.competitions.find_by_id(ronda.competition_id)
        )
        if competition is None:
            raise CompetitionNotFoundError(f"No existe competición con ID {ronda.competition_id}")
        return ronda, competition

    @staticmethod
    def equipo_de(competition: Competition, user_id: UserId) -> str | None:
        """De que equipo es capitan, o None si no capitanea ninguno.

        El equipo sale de aqui y NO de lo que pida el cliente: aceptarlo en el
        cuerpo dejaria entregar el sobre del rival. Quien capitanea que lo
        decide la entidad, que es donde vive esa regla.
        """
        for team in ("A", "B"):
            if competition.is_captain_of(team, user_id):
                return team
        return None

    async def comprobar_que_es_de_la_competicion(
        self, competition: Competition, user_id: UserId
    ) -> None:
        """Quien pregunta tiene que ser de esta competicion.

        Sin esto, probando identificadores se leia la sesion de cualquiera,
        incluida la de una privada.

        Raises:
            NotCompetitionParticipantError: Si no esta inscrito ni la organiza
        """
        if competition.is_creator(user_id):
            return
        inscripcion = await self._uow.enrollments.find_by_user_and_competition(
            user_id, competition.id
        )
        # APROBADA: una rechazada o retirada seguia valiendo de llave, y con
        # ella se leia quien ha entregado y, abiertos, los enfrentamientos
        if inscripcion is None or inscripcion.status != EnrollmentStatus.APPROVED:
            raise NotCompetitionParticipantError(
                "Esta sesión es de una competición en la que no participas"
            )

    async def jugadores_de(self, competition: Competition, team: str) -> list[UserId]:
        """Los del equipo que siguen inscritos.

        Raises:
            TeamsNotAssignedError: Si todavia no hay equipos repartidos. Sin
                esto el error acababa siendo «hay jugadores que no son de este
                equipo», que manda a buscar el fallo donde no esta
        """
        jugadores, hay_equipos = await TeamRoster.de_un_equipo(self._uow, competition.id, team)
        if not hay_equipos:
            raise TeamsNotAssignedError(
                "Todavía no hay equipos repartidos: primero se reparten y después van los sobres"
            )
        return jugadores

    async def handicaps_de(
        self, competition: Competition, jugadores: list[UserId]
    ) -> list[tuple[UserId, Decimal]]:
        """Cada jugador con el handicap que cuenta en esta competicion.

        El de la inscripcion si tiene uno propio, y si no el del jugador: la
        MISMA regla que usa la generacion de partidos. Mirar solo el propio
        dejaba a casi todo el mundo en cero —`custom_handicap` suele ser
        None—, y entonces el sobre automatico salia en el orden de la lista y
        no por handicap, que es lo que dice hacer.
        """
        inscripciones = {
            e.user_id: e
            for e in await self._uow.enrollments.find_by_competition_and_status(
                competition.id, EnrollmentStatus.APPROVED
            )
        }
        con_handicap = []
        for uid in jugadores:
            inscripcion = inscripciones.get(uid)
            if inscripcion is None:
                continue
            if inscripcion.custom_handicap is not None:
                con_handicap.append((uid, inscripcion.custom_handicap))
                continue
            user = await self._user_repo.find_by_id(uid)
            con_handicap.append(
                (
                    uid,
                    Decimal(str(user.handicap.value))
                    if user and user.handicap is not None
                    else Decimal("0"),
                )
            )
        return con_handicap

    @staticmethod
    def comprobar_que_la_sesion_admite_sobres(ronda: Round) -> None:
        """Con los partidos ya generados, los sobres no pintan nada.

        Entregar o abrir despues dejaria la sesion con unos partidos que no
        salen de ningun sobre y unos sobres que no son de esos partidos.

        Sin equipos repartidos —PENDING_TEAMS— NO se queja aqui: ese problema
        es otro y lo cuenta `jugadores_de` con su nombre.

        Raises:
            RoundAlreadyScheduledError: Si la sesion ya tiene partidos
        """
        if ronda.status in _CON_PARTIDOS_YA_HECHOS:
            raise RoundAlreadyScheduledError(
                "Esta sesión ya tiene sus partidos: los sobres se entregan antes de generarlos"
            )

    async def sobre_de(self, ronda: Round, team: str, crear: bool = False) -> Envelope | None:
        """El sobre de ese equipo para esa sesion, creandolo si hace falta."""
        sobre = await self._uow.envelopes.find_by_round_and_team_for_update(ronda.id, team)
        if sobre is None and crear:
            sobre = Envelope.create(
                competition_id=ronda.competition_id,
                round_id=ronda.id,
                team=team,
                match_format=ronda.match_format,
            )
            await self._uow.envelopes.add(sobre)
        return sobre

    def puede_abrirlos(
        self,
        competition: Competition,
        user_id: UserId,
        sobres: dict[str, Envelope],
        ronda: Round | None = None,
        is_admin: bool = False,
        sin_plazo: bool = False,
    ) -> bool:
        """Si esa persona puede abrir los sobres A MANO, ahora.

        **Nadie, con plazo que vencer** (BE #374, decidido el 24 sep): abrir
        antes de hora es decision de LOS DOS capitanes, y cada uno da su permiso
        al entregar; con los dos, se abren solos. Ni un capitan solo ni el
        organizador los abren a mano, tampoco con los dos sobres dentro.

        El capitan que no aparece no deja nada atascado: al vencer el plazo se
        abren solos y la aplicacion rellena lo que falte.

        **Salvo que no haya plazo que vencer** (`sin_plazo`): un campo sin zona
        horaria no da hora que calcular, asi que esos sobres no se abren solos
        NUNCA y la sesion se quedaria atascada —«generar partidos» la rechaza
        mientras queden sobres cerrados—. Ahi el que arbitra conserva la llave,
        que es la salida que ya estaba decidida antes del 23 sep.

        Quien: el organizador, un administrador o uno de los dos capitanes;
        quien solo mira, no.

        Vive aqui y no en cada caso de uso: la comprobacion de verdad y lo que
        la vista le cuenta a la pantalla tienen que decir lo mismo.
        """
        sobre_a, sobre_b = sobres.get("A"), sobres.get("B")
        if sobre_a and sobre_b and not sobre_a.is_sealed() and not sobre_b.is_sealed():
            return False
        # Con los partidos hechos ya no se abren: el endpoint lo rechaza, y
        # ofrecerlo seria mandar a la pantalla contra un 400
        if ronda is not None and ronda.status in _CON_PARTIDOS_YA_HECHOS:
            return False
        arbitra = is_admin or competition.is_creator(user_id)
        if not arbitra and self.equipo_de(competition, user_id) is None:
            return False
        return arbitra and sin_plazo

    async def los_equipos_cuadran(self, competition: Competition, por_fila: int) -> bool:
        """Si los dos equipos se pueden repartir en filas de `por_fila`.

        En parejas, un equipo impar no tiene sobre posible: el cruce va por
        posicion y alguien se quedaria fuera. Sin esto la sesion se atasca en
        silencio —no se entrega, el relleno revienta y el plazo vence sin abrir
        nada— y quien puede arreglarlo, el organizador, no lo ve por ningun
        lado.

        Sin equipos repartidos todavia no hay nada que no cuadre: eso lo dice
        su propio error cuando toca.
        """
        if por_fila == 1:
            return True
        try:
            for team in ("A", "B"):
                if len(await self.jugadores_de(competition, team)) % por_fila != 0:
                    return False
        except TeamsNotAssignedError:
            return True
        return True

    async def programado_para(self, ronda: Round, competition: Competition) -> datetime | None:
        """A que hora se abren solos los sobres de esa sesion."""
        zona = await self._zona_de(ronda)
        return EnvelopeRevealService.scheduled_for(ronda.round_date, ronda.session_type, zona)

    async def _zona_de(self, ronda: Round) -> str | None:
        """La zona del campo de ESA sesion, no la del primero de la competicion.

        Una competicion se puede jugar en varios campos, y cada sesion tiene el
        suyo. Con el primero mandando, una sesion heredaba la hora de otro
        sitio, y desde el 23 sep tambien la llave: el primero sin zona repartia
        salida de emergencia a sesiones que si tenian plazo.
        """
        if self._timezone is None:
            return None
        return await self._timezone.for_course(ronda.golf_course_id)

    def sin_plazo_que_vencer(self, programado: datetime | None) -> bool:
        """Si esa sesion no tiene hora a la que abrirse sola.

        Recibe el plazo ya calculado porque quien pregunta esto tambien lo
        enseña, y resolverlo dos veces son dos consultas a los campos.

        Sin servicio de zona —un caso de uso que no lo inyecta— la respuesta
        es que plazo hay, y entonces manda la regla estricta: que un cableado
        incompleto reparta llaves es como se pierde una regla sin que nadie lo
        note.
        """
        return self._timezone is not None and programado is None

    async def revelar_si_toca(
        self, ronda: Round, competition: Competition, sobres: dict[str, Envelope]
    ) -> bool:
        """Abre los sobres si ya toca, y dice si los ha abierto.

        Lo resuelve quien mira, como la anotacion se abre sola al llegar el
        primer golpe (BE #305): no hay ningun proceso de fondo mirando el reloj.

        **Nunca tumba la lectura.** Esto se llama desde el GET de la pantalla,
        asi que un motivo para no poder abrirlos —equipos sin repartir, un
        equipo impar en una sesion de parejas— se traga y se sigue pintando:
        el capitan que si entrego tiene que poder ver su sobre y el plazo. El
        camino manual si explica por que no puede.
        """
        sobre_a, sobre_b = sobres.get("A"), sobres.get("B")
        if sobre_a and sobre_b and not sobre_a.is_sealed() and not sobre_b.is_sealed():
            return False

        # Con los partidos ya hechos, unos sobres nuevos serian enfrentamientos
        # inventados que no se parecen a lo que se juega
        if ronda.status in _CON_PARTIDOS_YA_HECHOS:
            return False

        if not await self._toca_abrirlos(ronda, competition, sobres):
            return False

        try:
            # Se comprueba que los DOS se pueden preparar antes de tocar
            # ninguno: abrir uno y fallar al rellenar el otro dejaba la sesión
            # medio abierta, y de ahí no se sale —el organizador ya no puede
            # abrirlos porque uno «ya estaba abierto», y su capitán tampoco
            # puede corregir—
            relleno = await self._relleno_necesario(ronda, competition, sobres)
        except (TeamsNotAssignedError, OddTeamForPairsError, EmptyEnvelopeError):
            return False

        await self._abrir(ronda, competition, sobres, relleno)
        await self.generar_los_partidos(ronda, competition)
        return True

    async def generar_los_partidos(self, ronda: Round, competition: Competition) -> None:
        """Crea los partidos de una sesion recien abierta (BE #361).

        Con los sobres abiertos los enfrentamientos ya estan decididos: pulsar
        «Generar» solo los copiaba, y mientras nadie lo pulsaba la sesion podia
        llegar a su hora sin partidos.

        **El fallo no es mudo, ni tumba la apertura.** Esto ocurre dentro de la
        lectura de la pantalla o de la entrega del segundo sobre: si no se
        pueden crear, los sobres se quedan abiertos, la sesion sin partidos y el
        motivo apuntado en ella para que el organizador lo vea. Lo escrito a
        medias se deshace con el SAVEPOINT, no con la transaccion entera, que
        es la que lleva la apertura.
        """
        if self._generador is None:
            return
        # Cancelada o terminada no hay partidos que jugar: abrirse, se abren,
        # pero no hay nada que avisar
        if competition.status not in SE_JUEGA:
            # Reabierta, en cambio, volverá a cerrarse: sin un motivo apuntado
            # la sesión se quedaba atascada, porque en modo Ryder «Generar» solo
            # sale como reintento y los sobres ya están abiertos
            if (
                competition.status == CompetitionStatus.ACTIVE
                and ronda.status == RoundStatus.PENDING_MATCHES
            ):
                ronda.block_match_generation(
                    MatchGenerationBlock(reason=ENROLLMENT_OPEN, at=self.ahora.replace(tzinfo=None))
                )
                await self._uow.rounds.update(ronda)
            return
        # Solo la que espera partidos: en otro estado no hay nada que generar,
        # y apuntar un motivo ahi reventaria la lectura entera
        if ronda.status != RoundStatus.PENDING_MATCHES:
            return
        # Dos moviles abren a la vez: el segundo espera el bloqueo y sigue con
        # la sesion que leyo antes, sin partidos. Mirarlo en la base de datos
        # es lo que evita que borre y rehaga los del primero, con ids nuevos
        # que dejarian colgada a cualquier pantalla que ya tuviera los viejos
        if await self._uow.matches.find_by_round(ronda.id):
            return
        motivo: MatchGenerationBlock | None = None
        # El id se guarda ANTES: si el savepoint se deshace, SQLAlchemy caduca
        # lo que se toco dentro, y leer un atributo caducado es una carga
        # sincrona que en asincrono revienta (MissingGreenlet)
        round_id = ronda.id
        try:
            async with self._uow.savepoint():
                await self._generador.generar_dentro(
                    ronda, competition, refrescar_handicap_rfeg=False
                )
        except Exception as error:
            motivo = self._motivo(error)
        if motivo is None:
            return
        # Lo que la generacion cambio en memoria se ha deshecho en la base de
        # datos, pero no en el objeto: se vuelve a leer antes de apuntar nada
        ronda_de_verdad = await self._uow.rounds.find_by_id(round_id) or ronda
        ronda_de_verdad.block_match_generation(motivo)
        await self._uow.rounds.update(ronda_de_verdad)

    def _motivo(self, error: Exception) -> MatchGenerationBlock:
        """De la excepcion al motivo que se apunta en la sesion."""
        ahora = self.ahora.replace(tzinfo=None)
        if isinstance(error, PlayersWithoutTeeError):
            return MatchGenerationBlock(
                reason=PLAYERS_WITHOUT_TEE, players=tuple(error.players), at=ahora
            )
        if isinstance(error, InsufficientPlayersError):
            return MatchGenerationBlock(reason=NOT_ENOUGH_PLAYERS, at=ahora)
        if isinstance(error, NoTeamAssignmentError):
            return MatchGenerationBlock(reason=NO_TEAMS, at=ahora)
        if isinstance(error, NoGolfCourseForHandicapError):
            return MatchGenerationBlock(reason=NO_GOLF_COURSE, at=ahora)
        # Lo que no se esperaba se registra entero: el motivo solo dice que falló
        logger.exception("No se pudieron generar los partidos al abrir los sobres")
        return MatchGenerationBlock(reason=UNEXPECTED, at=ahora)

    async def _relleno_necesario(
        self, ronda: Round, competition: Competition, sobres: dict[str, Envelope]
    ) -> dict[str, list[tuple[UserId, Decimal]]]:
        """Lo que habria que rellenar en cada equipo, comprobando que se puede.

        No toca nada: solo reune los datos y deja que salte el motivo por el
        que no se podria —equipos sin repartir, un equipo vacio, o uno impar en
        una sesion de parejas—.

        Raises:
            TeamsNotAssignedError, EmptyEnvelopeError, OddTeamForPairsError
        """
        hace_falta: dict[str, list[tuple[UserId, Decimal]]] = {}
        for team in ("A", "B"):
            sobre = sobres.get(team)
            if sobre is not None and sobre.is_submitted():
                continue
            jugadores = await self.jugadores_de(competition, team)
            if not jugadores:
                raise EmptyEnvelopeError(f"El equipo {team} no tiene jugadores que colocar")
            por_fila = Envelope.players_per_row_for(ronda.match_format)
            if por_fila == EN_PAREJAS and len(jugadores) % EN_PAREJAS != 0:
                raise OddTeamForPairsError(
                    f"El equipo {team} tiene {len(jugadores)} jugadores y esta sesión es de "
                    "parejas: alguien se quedaría fuera"
                )
            hace_falta[team] = await self.handicaps_de(competition, jugadores)
        return hace_falta

    async def _toca_abrirlos(
        self, ronda: Round, competition: Competition, sobres: dict[str, Envelope]
    ) -> bool:
        """Si ha llegado el momento, sin tocar nada todavia.

        Lo barato primero: el reloj se mira ANTES de resolver la zona, listar
        las rondas y contar los partidos de la anterior. Esta pantalla se
        refresca, y dias antes del revelado todo eso seria trabajo tirado.
        """
        # La via corta: los DOS capitanes pidieron no esperar a la hora. Con
        # uno solo no vale, que el otro tiene derecho a su plazo (23 sep)
        if self._los_dos_quieren_sin_esperar(sobres):
            return True

        programado = await self.programado_para(ronda, competition)
        if programado is None or self.ahora < programado:
            return False

        comienzo = ScoringOpeningService.opens_at(
            ronda.round_date, ronda.session_type, await self._zona_de(ronda)
        )
        anterior_acabo = EnvelopeRevealService.previous_session_is_over(
            await self._partidos_pendientes_de_la_anterior(ronda, competition),
            comienzo,
            self.ahora,
        )
        return EnvelopeRevealService.is_due(programado, anterior_acabo, self.ahora)

    @staticmethod
    def _los_dos_quieren_sin_esperar(sobres: dict[str, Envelope]) -> bool:
        """Si los dos capitanes pidieron abrirlos en cuanto estuvieran los dos."""
        sobre_a, sobre_b = sobres.get("A"), sobres.get("B")
        return bool(
            sobre_a
            and sobre_b
            and sobre_a.is_submitted()
            and sobre_b.is_submitted()
            and sobre_a.reveal_when_both_ready
            and sobre_b.reveal_when_both_ready
        )

    async def _abrir(
        self,
        ronda: Round,
        competition: Competition,
        sobres: dict[str, Envelope],
        relleno: dict[str, list[tuple[UserId, Decimal]]],
    ) -> None:
        """Rellena lo que falte y abre los dos.

        Con la competicion bloqueada: aqui se CREAN sobres, y dos capitanes
        mirando la pantalla a la hora del revelado leerian los dos que no
        existen, los dos los crearian y uno reventaria contra la clave unica.
        `FOR UPDATE` no bloquea una fila que todavia no esta.
        """
        await self._uow.competitions.find_by_id_for_update(competition.id)
        ahora_sin_huso = self.ahora.replace(tzinfo=None)
        for team in ("A", "B"):
            sobre = await self.sobre_de(ronda, team, crear=True)
            if sobre is None:  # `crear=True` siempre devuelve uno; esto es para el tipo
                continue
            if not sobre.is_submitted():
                sobre.fill(relleno[team], ahora=ahora_sin_huso)
            sobre.reveal()
            await self._uow.envelopes.update(sobre)
            sobres[team] = sobre

    async def _partidos_pendientes_de_la_anterior(
        self, ronda: Round, competition: Competition
    ) -> int | None:
        """Cuantos partidos le quedan por terminar a la sesion anterior.

        Devuelve None cuando esta es la primera del torneo: ahi manda el reloj.
        """
        rondas = sorted(
            await self._uow.rounds.find_by_competition(competition.id),
            key=lambda r: (r.round_date, _ORDEN_DE_SESION.get(r.session_type, 0)),
        )
        anteriores = [
            r
            for r in rondas
            if (r.round_date, _ORDEN_DE_SESION.get(r.session_type, 0))
            < (ronda.round_date, _ORDEN_DE_SESION.get(ronda.session_type, 0))
        ]
        if not anteriores:
            return None
        anterior = anteriores[-1]
        if anterior.status == RoundStatus.COMPLETED:
            return 0
        partidos = await self._uow.matches.find_by_round(anterior.id)
        if not partidos:
            # Sin partidos generados NO es «ya se jugo»: es que ni siquiera ha
            # empezado. Contar cero pendientes abria los sobres de la siguiente
            # con la anterior por delante, que es lo que la espera evita
            return 1
        return sum(1 for m in partidos if not m.status.is_finished())
