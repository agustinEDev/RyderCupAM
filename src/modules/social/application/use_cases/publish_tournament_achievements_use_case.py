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


@dataclass(frozen=True)
class _TournamentRound:
    """Una vuelta de torneo reducida a lo que hace falta para juzgarla."""

    user_id: UserId
    match_id: str
    golf_course_id: str
    occurred_at: datetime
    holes: list[PlayedHole]
    # Con la publicacion apagada el logro se guarda solo para el
    visible_to_friends: bool
    # Lo que el logro necesita para abrir su tarjeta, si no es un partido de
    # Ryder: el grupo de stroke play y su torneo (bloque L)
    link: dict = field(default_factory=dict)


@dataclass
class _Grupos:
    """Lo leido de los grupos de stroke play de los inscritos (bloque L)."""

    # Por jugador, sus grupos de este torneo con la tarjeta entregada
    del_torneo: dict = field(default_factory=dict)
    # Por jugador, los otros torneos de stroke play en los que jugo
    otros_torneos: dict = field(default_factory=dict)
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

    async def execute(
        self,
        competition_id_raw: str,
        best_differential_before: dict[str, float | None] | None = None,
    ) -> int:
        """Publica lo que merezca publicarse y devuelve cuantos eventos creo."""
        best_before = best_differential_before or {}

        vueltas_por_jugador, estrena_torneo = await self._leer_vueltas(competition_id_raw)
        if not vueltas_por_jugador:
            return 0

        eventos: list[ActivityEvent] = []
        for user_id_raw, sin_ordenar in vueltas_por_jugador.items():
            # `FIRST_TOURNAMENT` y el record cuelgan de `vueltas[0]`, asi que
            # cual sea esa vuelta no puede depender del orden en que la base de
            # datos devolvio los partidos: si cambia entre ejecuciones, el mismo
            # logro colgaria de otro partido y la clave unica dejaria de
            # reconocerlo como repetido
            vueltas = sorted(sin_ordenar, key=lambda v: (v.occurred_at, v.match_id))
            marca_previa = best_before.get(user_id_raw)
            # El record se mide una vez por jugador, no una por vuelta: solo hay
            # una marca previa con la que comparar y la mejor de sus vueltas
            # nuevas es la que la batio
            record = await self._diferencial_si_es_record(vueltas[0].user_id, marca_previa)

            for indice, vuelta in enumerate(vueltas):
                contexto = RoundContext(
                    is_first_round_on_course=not await self._history.has_played_course_before(
                        vuelta.user_id, vuelta.golf_course_id, vuelta.match_id
                    ),
                    # Colgado del primer partido para que se publique una vez
                    is_first_tournament=indice == 0 and estrena_torneo.get(user_id_raw, False),
                    previous_best_differential=self._como_decimal(marca_previa),
                    differential=record if indice == 0 else None,
                )
                logros = self._detector.detect(holes=vuelta.holes, context=contexto)
                eventos.extend(self._a_eventos(logros, vuelta))

        if not eventos:
            return 0

        # Una fecha para toda la publicacion y el interruptor de ahora mismo
        eventos = await stamp_for_publication(self._user_uow, eventos)
        async with self._social_uow:
            await self._social_uow.activity_events.add_many(eventos)

        return len(eventos)

    async def _leer_vueltas(
        self, competition_id_raw: str
    ) -> tuple[dict[str, list[_TournamentRound]], dict[str, bool]]:
        """
        Las vueltas publicables del torneo, agrupadas por jugador, y quien
        estrena torneo con este.

        Salen de los partidos de la Ryder y de los grupos de salida del stroke
        play (bloque L): un torneo tiene unos u otros, y aqui da igual cuales.
        """
        vueltas: dict[str, list[_TournamentRound]] = {}
        estrena_torneo: dict[str, bool] = {}

        async with self._competition_uow, self._golf_course_uow, self._user_uow:
            competition_id = CompetitionId(competition_id_raw)
            competition = await self._competition_uow.competitions.find_by_id(competition_id)
            if competition is None or competition.status != CompetitionStatus.COMPLETED:
                return {}, {}

            enrollments = await self._competition_uow.enrollments.find_by_competition(
                competition_id
            )
            courses: dict = {}
            rounds: dict = {}
            grupos = await self._grupos(competition_id, [e.user_id for e in enrollments], rounds)

            for enrollment in enrollments:
                # Con la publicacion apagada tambien se publica, pero solo para
                # el: el interruptor decide lo que ven los demas
                user = await self._user_uow.users.find_by_id(enrollment.user_id)
                if user is None:
                    continue

                otros_torneos = set(grupos.otros_torneos.get(enrollment.user_id, set()))
                del_torneo = await self._partidos(
                    enrollment.user_id, competition_id, rounds, otros_torneos
                )

                sus_grupos = grupos.del_torneo.get(enrollment.user_id, [])
                if not del_torneo and not sus_grupos:
                    continue

                user_id_raw = str(enrollment.user_id.value)
                estrena_torneo[user_id_raw] = not otros_torneos

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

        return vueltas, estrena_torneo

    async def _partidos(
        self, user_id: UserId, competition_id: CompetitionId, rounds: dict, otros_torneos: set
    ) -> list:
        """
        Sus partidos de la Ryder en este torneo, con su ronda. Los de otros
        torneos solo dicen que ya los jugo: se apuntan en `otros_torneos`.
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
            if ronda.competition_id == competition_id:
                del_torneo.append((partido, ronda))
            else:
                otros_torneos.add(str(ronda.competition_id.value))
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
            tarjetas = partida.estados_de_tarjeta
            for user_id in buscados & set(partida.user_ids):
                estado = tarjetas[user_id]
                if partida.competition_id != competition_id:
                    if estado != EstadoDeTarjeta.NO_PRESENTADO:
                        leidos.otros_torneos.setdefault(user_id, set()).add(
                            str(partida.competition_id.value)
                        )
                elif estado == EstadoDeTarjeta.ENTREGADA:
                    # Ni los no presentados ni los retirados cuentan (L8)
                    leidos.del_torneo.setdefault(user_id, []).append(partida)

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
        faltan = {p.round_id for p in del_torneo.values()} - set(rounds)
        if faltan:
            for ronda in await self._competition_uow.rounds.find_by_ids(list(faltan)):
                rounds[ronda.id] = ronda
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
        return await self._vuelta_de(
            ronda,
            courses,
            scores_by_hole,
            partido.find_player(user_id),
            match_id=str(partido.id.value),
            user_id=user_id,
            visible_to_friends=visible_to_friends,
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
        if ronda.golf_course_id not in courses:
            courses[ronda.golf_course_id] = await self._golf_course_uow.golf_courses.find_by_id(
                ronda.golf_course_id
            )
        course = courses[ronda.golf_course_id]
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
        self, logros: list[DetectedAchievement], vuelta: _TournamentRound
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
            # En stroke play, `kind` TEE_GROUP, `group_id` y `competition_id`:
            # el logro abre la tarjeta del grupo, no la de un partido
            **vuelta.link,
        }
        if logro.count > 1:
            payload["count"] = logro.count
        if logro.holes:
            payload["holes"] = list(logro.holes)
        if logro.detail:
            payload.update(logro.detail)
        if logro.type == ActivityEventType.FIRST_TOURNAMENT:
            payload.pop("holes", None)
        return payload
