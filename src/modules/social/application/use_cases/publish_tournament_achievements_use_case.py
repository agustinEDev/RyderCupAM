"""Caso de Uso: Publicar en el feed los logros de un torneo terminado."""

import logging
from dataclasses import dataclass, field, replace
from datetime import datetime, time

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
    PlayedRound,
    as_iso,
    first_on_each_course,
    first_tournament_of_each,
    keep_only_the_oldest,
    lock_players,
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
from src.modules.social.domain.services.personal_best import record_context
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.countable_round import countable_holes
from src.shared.domain.utc_clock import utc_now

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
    # campo (`round_instant`). Ordena las vueltas del jugador
    instant: datetime
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
    # (grupo, jugador) -> hoyo -> golpes validados (None, una raya validada)
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
          reapertura anterior no llegara a borrarlo. Lo que se publico oculto
          vuelve oculto aunque se haya encendido la publicacion (lo apunta el
          repositorio al retirarlo, fallo del probador del 23 oct 2026).

        Tambien se recalcula si, mientras, otra publicacion de este mismo
        torneo escribio logros (revisor, 22 oct 2026): la herencia de un torneo
        anterior que se reabre se calcula despues y no se puede pisar.
        """
        competition_id = CompetitionId(competition_id_raw)
        for _ in range(MAX_INTENTOS):
            async with self._competition_uow:
                marca = await self._competition_uow.competitions.find_status_mark(competition_id)
            if marca is None or marca[0] != CompetitionStatus.COMPLETED:
                return 0

            calculado_en = utc_now()
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
                repo = self._social_uow.activity_events
                # Otra publicacion de este torneo escribio despues de que
                # empezara este calculo (p. ej. la herencia de una reapertura
                # de otro): lo calculado es viejo y se recalcula
                ultima = await repo.last_written_at(competition_id_raw, _LOGROS)
                if ahora == marca and (ultima is None or ultima <= calculado_en):
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
        (la reapertura ya los retiro, y en juego ya no cuenta). Por cada
        jugador del torneo:

        - en cada campo del torneo, la vuelta mas antigua que queda (de un
          torneo cerrado o una partida rapida);
        - su primer torneo cerrado.

        Por lotes: los inscritos, las rondas del torneo y el historial de todos
        de una vez. Volver a publicarlos es idempotente y pasa por la misma
        regla: si el heredero no es el mas antiguo, no se lleva nada.
        """
        competition_id = CompetitionId(competition_id_raw)
        async with self._competition_uow:
            enrollments = await self._competition_uow.enrollments.find_by_competition(
                competition_id
            )
            rondas_del_torneo = await self._competition_uow.rounds.find_by_competition(
                competition_id
            )
        campos = {str(r.golf_course_id.value) for r in rondas_del_torneo}
        rondas = await self._history.played_rounds([e.user_id for e in enrollments])

        torneos = {r.competition_id for r in first_tournament_of_each(rondas).values()}
        rapidas: set[str] = set()
        for (_, campo), primera in first_on_each_course(rondas).items():
            if campo not in campos:
                continue
            if primera.competition_id is None:
                rapidas.add(primera.source_id)
            else:
                torneos.add(primera.competition_id)
        torneos.discard(competition_id_raw)
        return Heirs(
            tournaments=sorted(t for t in torneos if t is not None),
            quick_matches=sorted(rapidas),
        )

    async def republish_exclusive(self, competition_id_raw: str, user_ids: list[UserId]) -> int:
        """
        Publica SOLO «campo nuevo» y «primer torneo» de este torneo para esos
        jugadores: es como hereda un torneo cerrado los de otro que se reabre
        (revision final, 22 oct 2026). Nunca recalcula ni sustituye sus demas
        logros —un record de entonces se recalcularia hoy con marcas de despues,
        y lo oculto se destaparia—, ni toca a otros jugadores. Lo que ya estaba
        publicado igual se queda como estaba; lo nuevo sale con el interruptor
        de ahora, salvo lo que se retiro oculto, que vuelve oculto. Devuelve
        cuantos publico.
        """
        competition_id = CompetitionId(competition_id_raw)
        if not user_ids:
            return 0
        # Sin mirar antes si esta cerrado: el historial solo da vueltas de
        # torneos cerrados, y con el candado se vuelve a comprobar
        async with self._user_uow:
            visibles = {
                u.id: u.share_activity for u in await self._user_uow.users.find_by_ids(user_ids)
            }
        eventos = await self._exclusivos(competition_id_raw, visibles)
        if not eventos:
            return 0
        eventos = await stamp_for_publication(self._user_uow, eventos)

        async with self._social_uow:
            repo = self._social_uow.activity_events
            # Los mismos candados, en el mismo orden, que una publicacion
            await repo.lock_scope(competition_id_raw)
            ahora = await self._competition_uow.competitions.find_status_mark(competition_id)
            if ahora is None or ahora[0] != CompetitionStatus.COMPLETED:
                return 0
            await lock_players(repo, list(visibles))
            eventos = await keep_only_the_oldest(
                repo,
                eventos,
                is_own=lambda e: e.payload.get("competition_id") == competition_id_raw,
            )
            await repo.add_many(eventos)
        return len(eventos)

    async def _calcular(self, competition_id_raw: str) -> tuple[list[ActivityEvent], list[UserId]]:
        """Los logros del torneo tal como esta ahora, sin publicar, y sus inscritos."""
        vueltas_por_jugador, visibles, jugadores = await self._leer_vueltas(competition_id_raw)

        eventos: list[ActivityEvent] = []
        for sin_ordenar in vueltas_por_jugador.values():
            # El record cuelga de la primera vuelta, asi que cual sea no puede
            # depender del orden en que la base de datos devolvio los partidos:
            # si cambia entre ejecuciones, el mismo logro colgaria de otra
            # vuelta y la clave unica dejaria de reconocerlo como repetido
            vueltas = sorted(sin_ordenar, key=lambda v: (v.instant, v.match_id))
            # El record se mide una vez por jugador, no una por vuelta: su mejor
            # vuelta del torneo contra lo jugado en dias ANTERIORES a su primer
            # dia (Agustin, 23 oct 2026). Se puede pedir en cualquier momento,
            # tambien al volver a cerrar un torneo reabierto
            record = record_context(
                await self._differentials.round_differentials(vueltas[0].user_id),
                lambda r: r.competition_id == competition_id_raw,
            )

            for indice, vuelta in enumerate(vueltas):
                contexto = record if indice == 0 else RoundContext()
                logros = self._detector.detect(holes=vuelta.holes, context=contexto)
                eventos.extend(self._a_eventos(logros, vuelta))

        eventos.extend(await self._exclusivos(competition_id_raw, visibles))
        return eventos, jugadores

    async def _exclusivos(
        self, competition_id_raw: str, visibles: dict[UserId, bool]
    ) -> list[ActivityEvent]:
        """
        «Campo nuevo» y «primer torneo» de este torneo: los de las vueltas en
        que sus jugadores pisaron por primera vez un campo o jugaron su primer
        torneo, segun el historial, que mira con el mismo criterio (al menos un
        hoyo, salvo NO_PRESENTADO) todo lo jugado. Puede ser una vuelta que no
        cuenta para los demas logros: un 4&3, una retirada con hoyos.
        """
        if not visibles:
            return []
        rondas = await self._history.played_rounds(list(visibles))
        eventos = [
            self._exclusivo(ActivityEventType.NEW_COURSE, primera, visibles[user_id])
            for (user_id, _), primera in first_on_each_course(rondas).items()
            if primera.competition_id == competition_id_raw
        ]
        eventos += [
            self._exclusivo(ActivityEventType.FIRST_TOURNAMENT, primera, visibles[user_id])
            for user_id, primera in first_tournament_of_each(rondas).items()
            if primera.competition_id == competition_id_raw
        ]
        return eventos

    @staticmethod
    def _exclusivo(tipo: ActivityEventType, ronda: PlayedRound, visible: bool) -> ActivityEvent:
        """Un logro exclusivo colgado de esa vuelta, con el contrato de siempre y `played_at`."""
        payload: dict = {
            "golf_course_id": ronda.golf_course_id,
            "holes_played": ronda.holes_played,
            "from_tournament": True,
            # `kind`, `competition_id`, en stroke play `group_id`, y `player_ids`
            # (Agustin, 22 oct 2026): abren la tarjeta a quien la jugo
            "kind": ronda.kind,
            "competition_id": ronda.competition_id,
            "player_ids": list(ronda.player_ids),
            PLAYED_AT: as_iso(ronda.instant),
        }
        if ronda.kind == "TEE_GROUP":
            payload["group_id"] = ronda.source_id
        dia = ronda.round_date or ronda.instant.date()
        return ActivityEvent.create(
            user_id=ronda.user_id,
            type=tipo,
            occurred_at=datetime.combine(dia, _MEDIODIA_UTC),
            source_match_id=ronda.source_id,
            payload=payload,
            visible_to_friends=visible,
        )

    async def _leer_vueltas(
        self, competition_id_raw: str
    ) -> tuple[dict[str, list[_TournamentRound]], dict[UserId, bool], list[UserId]]:
        """
        Las vueltas computables del torneo, agrupadas por jugador; si cada
        inscrito publica para sus amigos; y los inscritos.

        Salen de los partidos de la Ryder y de los grupos de salida del stroke
        play (bloque L): un torneo tiene unos u otros, y aqui da igual cuales.
        """
        vueltas: dict[str, list[_TournamentRound]] = {}
        visibles: dict[UserId, bool] = {}

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

            for enrollment in enrollments:
                # Con la publicacion apagada tambien se publica, pero solo para
                # el: el interruptor decide lo que ven los demas
                user = await self._user_uow.users.find_by_id(enrollment.user_id)
                if user is None:
                    continue
                visibles[enrollment.user_id] = user.share_activity

                del_torneo = await self._partidos(enrollment.user_id, competition_id, rounds)
                sus_grupos = grupos.del_torneo.get(enrollment.user_id, [])
                user_id_raw = str(enrollment.user_id.value)

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

        return vueltas, visibles, jugadores

    async def _campo(self, golf_course_id, courses: dict):
        """El campo, leido una vez por publicacion."""
        if golf_course_id not in courses:
            courses[golf_course_id] = await self._golf_course_uow.golf_courses.find_by_id(
                golf_course_id
            )
        return courses[golf_course_id]

    async def _partidos(self, user_id: UserId, competition_id: CompetitionId, rounds: dict) -> list:
        """Sus partidos de la Ryder en este torneo, con su ronda."""
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
            if ronda.competition_id == competition_id:
                del_torneo.append((partido, ronda))
        return del_torneo

    async def _grupos(
        self, competition_id: CompetitionId, user_ids: list[UserId], rounds: dict
    ) -> "_Grupos":
        """
        Los grupos de stroke play de este torneo con la tarjeta entregada,
        leidos de una vez para todos los inscritos, con sus golpes validados.
        Las rondas se guardan en `rounds` para no volver a leerlas.
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

        jugadas = {p.round_id for grupos in leidos.del_torneo.values() for p in grupos}
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
            # Solo lo validado (jugador y marcador coinciden). La raya validada
            # es un hoyo jugado, como en la partida rapida (Agustin, 23 oct
            # 2026); en Medal no la hay, porque el anotador la rechaza
            if golpe.validado:
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
        # Lo que el jugador envio, raya incluida (enviada y sin numero): es un
        # hoyo jugado, como en la partida rapida (Agustin, 23 oct 2026)
        scores_by_hole = {
            hole_score.hole_number: hole_score.own_score
            for hole_score in hole_scores
            if hole_score.own_submitted
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
            visible_to_friends=visible_to_friends,
            holes=[
                # La raya, juzgada como doble bogey, igual que en la partida
                # rapida: no da ningun logro
                PlayedHole.of(hole.number, hole.par, scores_by_hole[hole.number])
                for hole in jugados
            ],
        )

    def _a_eventos(
        self,
        logros: list[DetectedAchievement],
        vuelta: _TournamentRound,
    ) -> list[ActivityEvent]:
        return [
            ActivityEvent.create(
                user_id=vuelta.user_id,
                type=logro.type,
                occurred_at=vuelta.occurred_at,
                source_match_id=vuelta.match_id,
                payload=self._payload(logro, vuelta),
                visible_to_friends=vuelta.visible_to_friends,
            )
            for logro in logros
        ]

    @staticmethod
    def _payload(logro: DetectedAchievement, vuelta: _TournamentRound) -> dict:
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
        return payload


def _apuntar_grupo(leidos: _Grupos, partida, user_id: UserId, competition_id) -> None:
    """Un grupo de este torneo con la tarjeta entregada: de el salen sus logros (L8)."""
    if (
        partida.competition_id == competition_id
        and partida.estados_de_tarjeta[user_id] == EstadoDeTarjeta.ENTREGADA
    ):
        leidos.del_torneo.setdefault(user_id, []).append(partida)


def _ids(user_ids) -> list[str]:
    """Los ids de los jugadores, como texto y ordenados: el payload sale igual siempre."""
    return sorted({str(user_id.value) for user_id in user_ids})
