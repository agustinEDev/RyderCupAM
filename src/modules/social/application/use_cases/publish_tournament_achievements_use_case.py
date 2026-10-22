"""Caso de Uso: Publicar en el feed los logros de un torneo terminado."""

import logging
from dataclasses import dataclass, field, replace
from datetime import datetime, time
from decimal import Decimal

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.social.application.exclusive_achievements import (
    PLAYED_AT,
    as_iso,
    keep_only_the_oldest,
    lock_players,
    played_key,
    round_instant,
)
from src.modules.social.application.ports.player_course_history_interface import (
    PlayerCourseHistoryInterface,
)
from src.modules.social.application.ports.player_differentials_interface import (
    PlayerDifferentialsInterface,
)
from src.modules.social.application.publication import stamp_for_publication
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.domain.services.achievement_detector import (
    AchievementDetector,
    DetectedAchievement,
    PlayedHole,
    RoundContext,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.countable_round import countable_holes

logger = logging.getLogger(__name__)

# La ronda es una fecha, pero sale al JSON en UTC y con «Z»: a mediodia cae en
# el mismo dia en cualquier zona de -12 a +12; a medianoche, al oeste de
# Greenwich se veria el dia anterior
_MEDIODIA_UTC = time(12, 0)

# Cuantas vueltas del jugador se miran hacia atras para saber si estrena torneo.
MAX_HISTORY_LOOKUP = 200

# Cuantas veces se recalcula si el torneo cambia mientras se publica
MAX_INTENTOS = 3

# Los tipos que publica un torneo: los que se sustituyen en cada cierre
_LOGROS = frozenset(t for t in ActivityEventType if t.is_achievement)

# El torneo mas antiguo de un jugador: cuando jugo su primera vuelta y su id
_PrimerTorneo = tuple[datetime, str]


@dataclass(frozen=True)
class Heirs:
    """
    Quien puede heredar los logros exclusivos de un torneo que se reabre: los
    torneos cerrados y las partidas rapidas que ahora son lo mas antiguo.
    """

    tournaments: list[str]
    quick_matches: list[str]


@dataclass(frozen=True)
class _TournamentRound:
    """Una vuelta de torneo reducida a lo que hace falta para juzgarla."""

    user_id: UserId
    match_id: str
    golf_course_id: str
    occurred_at: datetime
    # Cuando se jugo de verdad, en UTC: la apertura de su sesion en la zona del
    # campo (`round_instant`). Ordena las vueltas y fecha los logros exclusivos
    instant: datetime
    # La zona del campo: situa en el las rondas de otros torneos del historial
    timezone: str | None
    holes: list[PlayedHole]
    # Con la publicacion apagada el logro se guarda solo para el
    visible_to_friends: bool
    # Lo que el logro necesita para abrir su tarjeta o la ficha del torneo:
    # `kind` (MATCH o TEE_GROUP), `competition_id`, en stroke play `group_id`,
    # y `player_ids`: quien jugo ese partido o grupo puede abrir la tarjeta
    link: dict = field(default_factory=dict)


@dataclass
class _Grupos:
    """Lo leido de los grupos de stroke play de los inscritos (bloque L)."""

    # Por jugador, sus grupos de este torneo con la tarjeta entregada
    del_torneo: dict = field(default_factory=dict)
    # Por jugador, los torneos de stroke play en los que jugo (este tambien),
    # con las rondas en que lo hizo con cualquier tarjeta salvo NO_PRESENTADO:
    # torneo -> {ronda}. Deciden cual fue su primer torneo
    jugados: dict = field(default_factory=dict)
    # (grupo, jugador) -> hoyo -> golpes validados
    validados: dict = field(default_factory=dict)


class PublishTournamentAchievementsUseCase:
    """
    Publica los logros de un torneo recien terminado.

    Un torneo son varias vueltas por jugador, no una: cada partido terminado se
    juzga por separado y lleva su propio `source_match_id`, que es lo que hace
    que reprocesar el cierre no duplique nada.

    `FIRST_TOURNAMENT` se publica **una sola vez por jugador**, colgado de su
    primer partido. Colgarlo de todos llenaria el feed de la misma noticia
    repetida, y no colgarlo de ninguno lo dejaria sin idempotencia.

    «Campo nuevo» y «primer torneo» son exclusivos por fecha real (22 oct
    2026): son de la vuelta mas antigua en el campo y del torneo mas antiguo,
    y al publicar se comparan con lo ya publicado (`keep_only_the_oldest`).

    Se publican los golpes propios (`own_score`) y no el neto validado: el neto
    solo existe cuando el rival ha cerrado la validacion cruzada, asi que media
    tarjeta legitima se quedaria fuera por un tramite que no es del jugador.
    """

    def __init__(
        self,
        social_uow: SocialUnitOfWorkInterface,
        competition_uow: CompetitionUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        differentials: PlayerDifferentialsInterface,
        history: PlayerCourseHistoryInterface,
        detector: AchievementDetector | None = None,
    ):
        self._social_uow = social_uow
        self._competition_uow = competition_uow
        self._golf_course_uow = golf_course_uow
        self._user_uow = user_uow
        self._differentials = differentials
        self._history = history
        self._detector = detector or AchievementDetector()

    async def execute(self, competition_id_raw: str) -> int:
        """
        Publica los logros del ultimo cierre del torneo y devuelve cuantos son.

        Calcularlos lleva un rato y no se hace bajo el candado del torneo: en
        ese hueco se puede reabrir, corregir una tarjeta y volver a cerrar
        (revision final del 22 oct 2026). Por eso, ya con el candado y en la
        misma transaccion que escribe, se vuelve a leer la marca del cierre
        (estado y ultima modificacion):

        - Ya no esta cerrado: no se publica nada. La reapertura borra lo suyo.
        - Sigue cerrado pero la marca cambio (se cerro otra vez, o se toco):
          lo calculado es viejo y se recalcula, hasta `MAX_INTENTOS`.
        - Igual: se sustituye lo publicado del torneo por lo calculado. Lo que
          ya estaba igual no se toca; lo que sobra se borra, aunque una
          reapertura anterior no llegara a borrarlo.
        """
        competition_id = CompetitionId(competition_id_raw)
        for _ in range(MAX_INTENTOS):
            async with self._competition_uow:
                marca = await self._competition_uow.competitions.find_status_mark(competition_id)
            if marca is None or marca[0] != CompetitionStatus.COMPLETED:
                return 0

            eventos, jugadores = await self._calcular(competition_id_raw)
            if eventos:
                # Una fecha para toda la publicacion y el interruptor de ahora
                eventos = await stamp_for_publication(self._user_uow, eventos)

            async with self._social_uow:
                # El mismo candado que la reapertura y los avisos del torneo
                await self._social_uow.activity_events.lock_scope(competition_id_raw)
                # Comparten sesion: esta lectura va dentro de la transaccion
                # que tiene el candado, y no abre la suya (que la cerraria)
                ahora = await self._competition_uow.competitions.find_status_mark(competition_id)
                if ahora is None or ahora[0] != CompetitionStatus.COMPLETED:
                    return 0
                if ahora == marca:
                    repo = self._social_uow.activity_events
                    # Despues del candado del torneo, los de sus jugadores, en
                    # orden: lo exclusivo se compara y se retira bajo ellos
                    await lock_players(repo, jugadores)
                    eventos = await keep_only_the_oldest(
                        repo,
                        eventos,
                        is_own=lambda e: e.payload.get("competition_id") == competition_id_raw,
                    )
                    await repo.replace_for_competition(competition_id_raw, _LOGROS, eventos)
                    return len(eventos)

        logger.warning(
            "Tournament %s kept changing while publishing its achievements", competition_id_raw
        )
        return 0

    async def heirs_of(self, competition_id_raw: str) -> Heirs:
        """
        Quien hereda los logros exclusivos de un torneo que se acaba de reabrir
        (la reapertura ya los retiro). Por cada jugador del torneo:

        - en cada campo en que jugo, la vuelta mas antigua que queda (de un
          torneo cerrado o una partida rapida);
        - su torneo cerrado mas antiguo.

        Volver a publicarlos es idempotente y pasa por la misma regla: si el
        heredero no es el mas antiguo publicable, no se lleva nada.
        """
        competition_id = CompetitionId(competition_id_raw)
        async with self._competition_uow, self._golf_course_uow:
            enrollments = await self._competition_uow.enrollments.find_by_competition(
                competition_id
            )
            user_ids = [e.user_id for e in enrollments]
            rounds: dict = {}
            courses: dict = {}
            jugados = await self._jugados(competition_id, user_ids, rounds)
            primeros = await self._primeros_torneos(jugados, rounds, courses)
            campos = {
                (user_id, de_la_ronda.golf_course_id)
                for user_id in user_ids
                for ronda_id in jugados.get(str(user_id.value), {}).get(competition_id_raw, ())
                if (de_la_ronda := rounds.get(ronda_id)) is not None
            }
            for _, golf_course_id in campos:
                await self._campo(golf_course_id, courses)

        torneos = {primero[1] for primero in primeros.values() if primero is not None}
        rapidas: set[str] = set()
        for user_id, golf_course_id in campos:
            course = courses.get(golf_course_id)
            primera = await self._history.first_round_on_course(
                user_id, str(golf_course_id.value), course.timezone if course else None
            )
            if primera is None:
                continue
            if primera.competition_id is None:
                rapidas.add(primera.source_id)
            else:
                torneos.add(primera.competition_id)
        torneos.discard(competition_id_raw)
        return Heirs(tournaments=sorted(torneos), quick_matches=sorted(rapidas))

    async def _calcular(self, competition_id_raw: str) -> tuple[list[ActivityEvent], list[UserId]]:
        """Los logros del torneo tal como esta ahora, sin publicar, y sus inscritos."""
        vueltas_por_jugador, primer_torneo, jugadores = await self._leer_vueltas(competition_id_raw)
        if not vueltas_por_jugador:
            return [], jugadores

        eventos: list[ActivityEvent] = []
        for user_id_raw, sin_ordenar in vueltas_por_jugador.items():
            # `FIRST_TOURNAMENT`, el record y el campo nuevo cuelgan de la
            # primera vuelta, asi que cual sea no puede depender del orden en que
            # la base de datos devolvio los partidos: si cambia entre
            # ejecuciones, el mismo logro colgaria de otra vuelta y la clave
            # unica dejaria de reconocerlo como repetido
            # Por cuando se jugo de verdad: dos rondas el mismo dia, la de la
            # manana primero (22 oct 2026)
            vueltas = sorted(sin_ordenar, key=lambda v: (v.instant, v.match_id))
            # La marca de ANTES del torneo, sin ninguna de sus vueltas
            # (decision del 22 oct 2026): se puede pedir en cualquier momento,
            # tambien al volver a cerrar un torneo reabierto
            marca_previa = await self._differentials.best_differential(
                vueltas[0].user_id, excluding_competition_id=competition_id_raw
            )
            # El record se mide una vez por jugador, no una por vuelta: solo hay
            # una marca previa con la que comparar y la mejor de sus vueltas
            # nuevas es la que la batio
            record = await self._diferencial_si_es_record(vueltas[0].user_id, marca_previa)
            # «Primer torneo»: si este es su torneo cerrado mas antiguo, fechado
            # con su primera vuelta jugada
            primero = primer_torneo.get(user_id_raw)
            torneo_at = primero[0] if primero is not None else None
            estrena_torneo = primero is not None and primero[1] == competition_id_raw
            # «Campo nuevo» se mira una vez por campo: con la primera vuelta
            # del torneo en el, que es la unica que puede ser la mas antigua
            campos_del_torneo: set[str] = set()

            for indice, vuelta in enumerate(vueltas):
                primera_en_el_campo = vuelta.golf_course_id not in campos_del_torneo
                campos_del_torneo.add(vuelta.golf_course_id)
                contexto = RoundContext(
                    is_first_round_on_course=primera_en_el_campo
                    and await self._estrena_campo(vuelta, competition_id_raw),
                    # Colgado del primer partido para que se publique una vez
                    is_first_tournament=indice == 0 and estrena_torneo,
                    previous_best_differential=self._como_decimal(marca_previa),
                    differential=record if indice == 0 else None,
                )
                logros = self._detector.detect(holes=vuelta.holes, context=contexto)
                eventos.extend(
                    self._a_eventos(logros, vuelta, torneo_at if estrena_torneo else None)
                )

        return eventos, jugadores

    async def _estrena_campo(self, vuelta: _TournamentRound, competition_id_raw: str) -> bool:
        """Si es la vuelta mas antigua del jugador en el campo."""
        primera = await self._history.first_round_on_course(
            vuelta.user_id, vuelta.golf_course_id, vuelta.timezone
        )
        return primera is None or primera.key >= played_key(
            vuelta.instant, competition_id_raw, vuelta.match_id
        )

    async def _leer_vueltas(
        self, competition_id_raw: str
    ) -> tuple[dict[str, list[_TournamentRound]], dict[str, _PrimerTorneo | None], list[UserId]]:
        """
        Las vueltas publicables del torneo, agrupadas por jugador; el torneo
        cerrado mas antiguo de cada uno; y los inscritos.

        Salen de los partidos de la Ryder y de los grupos de salida del stroke
        play (bloque L): un torneo tiene unos u otros, y aqui da igual cuales.
        """
        vueltas: dict[str, list[_TournamentRound]] = {}

        async with self._competition_uow, self._golf_course_uow, self._user_uow:
            competition_id = CompetitionId(competition_id_raw)
            competition = await self._competition_uow.competitions.find_by_id(competition_id)
            if competition is None or competition.status != CompetitionStatus.COMPLETED:
                return {}, {}, []

            enrollments = await self._competition_uow.enrollments.find_by_competition(
                competition_id
            )
            jugadores = [e.user_id for e in enrollments]
            courses: dict = {}
            rounds: dict = {}
            grupos = await self._grupos(competition_id, jugadores, rounds)
            jugados: dict[str, dict[str, set]] = {}

            for enrollment in enrollments:
                # Con la publicacion apagada tambien se publica, pero solo para
                # el: el interruptor decide lo que ven los demas
                user = await self._user_uow.users.find_by_id(enrollment.user_id)
                if user is None:
                    continue

                suyos = {
                    torneo: set(rondas)
                    for torneo, rondas in grupos.jugados.get(enrollment.user_id, {}).items()
                }
                del_torneo = await self._partidos(enrollment.user_id, competition_id, rounds, suyos)

                sus_grupos = grupos.del_torneo.get(enrollment.user_id, [])
                if not del_torneo and not sus_grupos:
                    continue

                user_id_raw = str(enrollment.user_id.value)
                jugados[user_id_raw] = suyos

                for partido, ronda in del_torneo:
                    vuelta = await self._a_vuelta(
                        partido, ronda, enrollment.user_id, courses, user.share_activity
                    )
                    if vuelta is not None:
                        vueltas.setdefault(user_id_raw, []).append(vuelta)

                for grupo in sus_grupos:
                    vuelta = await self._grupo_a_vuelta(
                        grupo,
                        rounds.get(grupo.round_id),
                        enrollment.user_id,
                        courses,
                        grupos.validados,
                        user.share_activity,
                    )
                    if vuelta is not None:
                        vueltas.setdefault(user_id_raw, []).append(vuelta)

            primer_torneo = await self._primeros_torneos(jugados, rounds, courses)

        return vueltas, primer_torneo, jugadores

    async def _jugados(
        self, competition_id: CompetitionId, user_ids: list[UserId], rounds: dict
    ) -> dict[str, dict[str, set]]:
        """Por jugador, los torneos en que jugo (Ryder y stroke play) con sus rondas."""
        grupos = await self._grupos(competition_id, user_ids, rounds)
        jugados: dict[str, dict[str, set]] = {}
        for user_id in user_ids:
            suyos = {
                torneo: set(rondas) for torneo, rondas in grupos.jugados.get(user_id, {}).items()
            }
            await self._partidos(user_id, competition_id, rounds, suyos)
            jugados[str(user_id.value)] = suyos
        return jugados

    async def _primeros_torneos(
        self, jugados: dict[str, dict[str, set]], rounds: dict, courses: dict
    ) -> dict[str, _PrimerTorneo | None]:
        """
        Por jugador, su torneo CERRADO mas antiguo: el de su primera vuelta
        jugada (salvo NO_PRESENTADO) en hora real, y con el mismo instante el
        de id menor. Uno en juego aun no ha publicado nada y uno cancelado
        nunca lo hara (22 oct 2026). Las rondas y los torneos, de una vez.
        """
        faltan = {r for suyos in jugados.values() for rs in suyos.values() for r in rs} - set(
            rounds
        )
        if faltan:
            for ronda in await self._competition_uow.rounds.find_by_ids(list(faltan)):
                rounds[ronda.id] = ronda
        ids = {torneo for suyos in jugados.values() for torneo in suyos}
        cerrados = (
            {
                str(t.id.value)
                for t in await self._competition_uow.competitions.find_by_ids(
                    [CompetitionId(crudo) for crudo in ids]
                )
                if t.status == CompetitionStatus.COMPLETED
            }
            if ids
            else set()
        )

        primeros: dict[str, _PrimerTorneo | None] = {}
        for user_id_raw, suyos in jugados.items():
            candidatos: list[_PrimerTorneo] = []
            for torneo, rondas in suyos.items():
                if torneo not in cerrados:
                    continue
                instantes = [
                    await self._instante(jugada, courses)
                    for r in rondas
                    if (jugada := rounds.get(r)) is not None
                ]
                if instantes:
                    candidatos.append((min(instantes), torneo))
            primeros[user_id_raw] = min(candidatos, default=None)
        return primeros

    async def _instante(self, ronda, courses: dict) -> datetime:
        """Cuando se jugo una ronda, con la zona de su campo."""
        course = await self._campo(ronda.golf_course_id, courses)
        return round_instant(
            ronda.round_date, ronda.session_type, course.timezone if course else None
        )

    async def _campo(self, golf_course_id, courses: dict):
        """El campo, leido una vez por publicacion."""
        if golf_course_id not in courses:
            courses[golf_course_id] = await self._golf_course_uow.golf_courses.find_by_id(
                golf_course_id
            )
        return courses[golf_course_id]

    async def _partidos(
        self, user_id: UserId, competition_id: CompetitionId, rounds: dict, jugados: dict
    ) -> list:
        """
        Sus partidos de la Ryder en este torneo, con su ronda. Todos, de este y
        de otros torneos, se apuntan en `jugados` (torneo -> {ronda}): dicen en
        que torneos jugo y cuando.
        """
        partidos = await self._competition_uow.matches.find_completed_for_player(
            user_id, limit=MAX_HISTORY_LOOKUP
        )
        del_torneo = []
        for partido in partidos:
            if partido.round_id not in rounds:
                rounds[partido.round_id] = await self._competition_uow.rounds.find_by_id(
                    partido.round_id
                )
            ronda = rounds[partido.round_id]
            if ronda is None:
                continue
            jugados.setdefault(str(ronda.competition_id.value), set()).add(ronda.id)
            if ronda.competition_id == competition_id:
                del_torneo.append((partido, ronda))
        return del_torneo

    async def _grupos(
        self, competition_id: CompetitionId, user_ids: list[UserId], rounds: dict
    ) -> "_Grupos":
        """
        Los grupos de stroke play que importan para publicar, leidos de una vez
        para todos los inscritos: los de este torneo, con sus golpes validados,
        y en que otros torneos jugo ya cada uno (para el primer torneo).

        Un no presentado no jugo ese torneo, asi que no le quita el estreno a
        nadie; quien se retiro si lo jugo. Las rondas se guardan en `rounds`
        para no volver a leerlas.
        """
        leidos = _Grupos()
        if not user_ids:
            return leidos
        buscados = set(user_ids)
        partidas = await self._competition_uow.partidas.completadas_de_jugadores(user_ids)
        if not partidas:
            return leidos

        for partida in partidas:
            for user_id in buscados & set(partida.user_ids):
                _apuntar_grupo(leidos, partida, user_id, competition_id)

        jugadas = {
            r for torneos in leidos.jugados.values() for rondas in torneos.values() for r in rondas
        }
        faltan = jugadas - set(rounds)
        if faltan:
            for ronda in await self._competition_uow.rounds.find_by_ids(list(faltan)):
                rounds[ronda.id] = ronda
        del_torneo = {p.id: p for grupos in leidos.del_torneo.values() for p in grupos}
        if not del_torneo:
            return leidos
        for golpe in await self._competition_uow.golpes_de_partida.de_las_partidas(
            list(del_torneo)
        ):
            # Solo lo validado (jugador y marcador coinciden) y con numero: la
            # raya deja el hoyo sin golpes, como en la Ryder (`own_score`)
            if golpe.validado and golpe.golpes_validados is not None:
                leidos.validados.setdefault((golpe.partida_id, golpe.user_id), {})[golpe.hoyo] = (
                    golpe.golpes_validados
                )
        return leidos

    async def _grupo_a_vuelta(
        self,
        grupo,
        ronda,
        user_id: UserId,
        courses: dict,
        validados: dict,
        visible_to_friends: bool,
    ) -> _TournamentRound | None:
        """
        La vuelta de un jugador en su grupo de stroke play, o None si su
        tarjeta no cuenta: la misma regla que un partido (`countable_holes`
        sobre la tarjeta de su barra), con los golpes validados del grupo.
        """
        if ronda is None:
            return None
        jugador = next((j for j in grupo.jugadores if j.user_id == user_id), None)
        vuelta = await self._vuelta_de(
            ronda,
            courses,
            validados.get((grupo.id, user_id), {}),
            jugador,
            match_id=str(grupo.id.value),
            user_id=user_id,
            visible_to_friends=visible_to_friends,
        )
        if vuelta is None:
            return None
        return replace(
            vuelta,
            link={
                "kind": "TEE_GROUP",
                "group_id": str(grupo.id.value),
                "competition_id": str(grupo.competition_id.value),
                "player_ids": _ids(grupo.user_ids),
            },
        )

    async def _a_vuelta(
        self, partido, ronda, user_id: UserId, courses: dict, visible_to_friends: bool
    ) -> _TournamentRound | None:
        """La vuelta de un jugador en un partido, o None si su tarjeta no cuenta."""
        hole_scores = await self._competition_uow.hole_scores.find_by_match_and_player(
            partido.id, user_id
        )
        scores_by_hole = {
            hole_score.hole_number: hole_score.own_score
            for hole_score in hole_scores
            if hole_score.own_score is not None
        }
        vuelta = await self._vuelta_de(
            ronda,
            courses,
            scores_by_hole,
            partido.find_player(user_id),
            match_id=str(partido.id.value),
            user_id=user_id,
            visible_to_friends=visible_to_friends,
        )
        if vuelta is None:
            return None
        return replace(
            vuelta,
            link={
                "kind": "MATCH",
                "competition_id": str(ronda.competition_id.value),
                "player_ids": _ids(
                    p.user_id for p in (*partido.team_a_players, *partido.team_b_players)
                ),
            },
        )

    async def _vuelta_de(
        self,
        ronda,
        courses: dict,
        scores_by_hole: dict,
        jugador,
        *,
        match_id: str,
        user_id: UserId,
        visible_to_friends: bool,
    ) -> _TournamentRound | None:
        """
        Una tarjeta convertida en vuelta, o None si no forma una: la comparten
        el partido de la Ryder y el grupo de stroke play.

        `courses` cachea los campos entre partidos: un torneo entero suele
        jugarse en uno o dos, y sin esto se consultaria el mismo por cada
        partido de cada jugador.
        """
        course = await self._campo(ronda.golf_course_id, courses)
        if course is None:
            return None

        # El par y el índice son de la barra que juega: un birdie se mide
        # contra el par de su tarjeta, no contra el del campo
        jugados = countable_holes(
            scores_by_hole,
            course.hole_card_for(jugador.tee_color, jugador.tee_gender)
            if jugador is not None
            else course.reference_card,
        )
        if jugados is None:
            return None

        return _TournamentRound(
            user_id=user_id,
            match_id=match_id,
            golf_course_id=str(ronda.golf_course_id.value),
            occurred_at=datetime.combine(ronda.round_date, _MEDIODIA_UTC),
            instant=round_instant(ronda.round_date, ronda.session_type, course.timezone),
            timezone=course.timezone,
            visible_to_friends=visible_to_friends,
            holes=[
                PlayedHole(
                    number=hole.number,
                    par=hole.par,
                    strokes=scores_by_hole[hole.number],
                )
                for hole in jugados
            ],
        )

    async def _diferencial_si_es_record(
        self, user_id: UserId, best_before: float | None
    ) -> Decimal | None:
        """El diferencial del torneo, solo cuando ha batido el record."""
        if best_before is None:
            return None

        ahora = await self._differentials.best_differential(user_id)
        if ahora is None or ahora >= best_before:
            return None
        return self._como_decimal(ahora)

    @staticmethod
    def _como_decimal(value: float | None) -> Decimal | None:
        return None if value is None else Decimal(str(value))

    def _a_eventos(
        self,
        logros: list[DetectedAchievement],
        vuelta: _TournamentRound,
        primer_torneo_at: datetime | None,
    ) -> list[ActivityEvent]:
        return [
            ActivityEvent.create(
                user_id=vuelta.user_id,
                type=logro.type,
                occurred_at=vuelta.occurred_at,
                source_match_id=vuelta.match_id,
                payload=self._payload(logro, vuelta, primer_torneo_at),
                visible_to_friends=vuelta.visible_to_friends,
            )
            for logro in logros
        ]

    @staticmethod
    def _payload(
        logro: DetectedAchievement, vuelta: _TournamentRound, primer_torneo_at: datetime | None
    ) -> dict:
        payload: dict = {
            "golf_course_id": vuelta.golf_course_id,
            "holes_played": len(vuelta.holes),
            # Distingue en el feed una vuelta de torneo de una entre amigos
            "from_tournament": True,
            # `kind` (MATCH o TEE_GROUP), `competition_id`, en stroke play
            # `group_id`, y `player_ids` (todos los del partido o grupo, el
            # autor incluido, ordenados): el logro abre la tarjeta a quien la
            # jugo y, a los demas, la ficha del torneo (Agustin, 22 oct 2026)
            **vuelta.link,
        }
        if logro.count > 1:
            payload["count"] = logro.count
        if logro.holes:
            payload["holes"] = list(logro.holes)
        if logro.detail:
            payload.update(logro.detail)
        # Cuando se jugo, en UTC: con esto se compara lo publicado (22 oct
        # 2026). «Primer torneo», con la primera vuelta jugada del torneo
        if logro.type == ActivityEventType.NEW_COURSE:
            payload[PLAYED_AT] = as_iso(vuelta.instant)
        if logro.type == ActivityEventType.FIRST_TOURNAMENT:
            payload.pop("holes", None)
            payload[PLAYED_AT] = as_iso(primer_torneo_at or vuelta.instant)
        return payload


def _apuntar_grupo(leidos: _Grupos, partida, user_id: UserId, competition_id) -> None:
    """
    Donde va un grupo terminado de un inscrito: salvo NO_PRESENTADO, el torneo
    y la ronda en que jugo; y, si es de este y entrego la tarjeta, el grupo del
    que salen sus logros.
    """
    estado = partida.estados_de_tarjeta[user_id]
    if estado == EstadoDeTarjeta.NO_PRESENTADO:
        return
    leidos.jugados.setdefault(user_id, {}).setdefault(str(partida.competition_id.value), set()).add(
        partida.round_id
    )
    if partida.competition_id != competition_id:
        return
    if estado == EstadoDeTarjeta.ENTREGADA:
        # Ni los no presentados ni los retirados cuentan (L8)
        leidos.del_torneo.setdefault(user_id, []).append(partida)


def _ids(user_ids) -> list[str]:
    """Los ids de los jugadores, como texto y ordenados: el payload sale igual siempre."""
    return sorted({str(user_id.value) for user_id in user_ids})
