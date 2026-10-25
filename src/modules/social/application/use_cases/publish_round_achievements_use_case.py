"""Caso de Uso: Publicar en el feed los logros de una vuelta terminada."""

from dataclasses import dataclass
from datetime import datetime

from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.social.application.exclusive_achievements import (
    EXCLUSIVE_TYPES,
    PLAYED_AT,
    as_iso,
    first_on_each_course,
    keep_only_the_oldest,
    lock_players,
    utc_naive,
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
)
from src.modules.social.domain.services.personal_best import record_context
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.countable_round import countable_holes

# Cuántas partidas del jugador se miran para saber si estrena campo. Un jugador
# con más historia que esto ya no estrena nada que importe recordar.
MAX_HISTORY_LOOKUP = 200


@dataclass(frozen=True)
class _RoundToJudge:
    """
    La vuelta de un jugador reducida a lo que hace falta para juzgarla.

    Existe para que la lectura y el juicio no se mezclen: aquí ya no hay
    entidades de `quick_match` ni de `golf_course`, así que juzgar no puede
    volver a la base de datos sin querer.
    """

    user_id: UserId
    match_id: str
    golf_course_id: str
    occurred_at: datetime
    holes: list[PlayedHole]
    # Con la publicacion apagada el logro se guarda solo para el
    visible_to_friends: bool


class PublishRoundAchievementsUseCase:
    """
    Publica los logros de una partida rápida recién terminada.

    **Solo se publica hacia delante** (decisión de producto en BE #175): no hay
    backfill, así que este caso de uso es el único que crea eventos y solo se
    dispara al cerrar una partida. El feed nace vacío y se llena solo.

    Publica para **todos los participantes con cuenta**, no solo para quien
    cierra la partida: el birdie es de quien lo hizo. Los invitados no tienen
    dónde publicar.

    Nunca interrumpe el cierre de la partida. Un fallo aquí no puede impedir que
    una partida se dé por terminada — el feed es accesorio y la tarjeta no.
    """

    def __init__(
        self,
        social_uow: SocialUnitOfWorkInterface,
        quick_match_uow: QuickMatchUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        differentials: PlayerDifferentialsInterface,
        history: PlayerCourseHistoryInterface,
        detector: AchievementDetector | None = None,
    ):
        self._social_uow = social_uow
        self._quick_match_uow = quick_match_uow
        self._golf_course_uow = golf_course_uow
        self._user_uow = user_uow
        self._differentials = differentials
        self._history = history
        self._detector = detector or AchievementDetector()

    async def execute(
        self,
        quick_match_id_raw: str,
        only_new_course: bool = False,
        published_at: datetime | None = None,
    ) -> int:
        """
        Publica lo que merezca publicarse y devuelve cuántos eventos creó.

        El récord se mide contra las vueltas de días ANTERIORES a esta
        (`record_context`, Agustín, 23 oct 2026): una ya cerrada pero jugada
        después no es la marca que esta mejora.

        `only_new_course` publica solo su «campo nuevo»: es como hereda una
        partida rapida el de un torneo que se reabre, sin volver a publicar el
        resto de sus logros.

        «Campo nuevo» es exclusivo por fecha real (22 oct 2026): sale si esta
        partida es la primera vez que el jugador piso el campo (al menos un
        hoyo, aunque la tarjeta no valga para los demas logros) y, bajo el
        candado del jugador, solo si no hay otro publicado anterior; los
        posteriores se retiran (`keep_only_the_oldest`).

        `published_at`, la fecha con la que sale en Actividad si no es ahora.
        """
        # Fase 1: leer. Todo lo que hace falta de la partida, en un solo paso y
        # con las unidades de trabajo abiertas lo justo
        vueltas, visibles = await self._leer_vueltas(quick_match_id_raw)
        if only_new_course:
            # Solo lo exclusivo: no se juzgan las tarjetas
            vueltas = []

        # Fase 2: juzgar. Fuera de cualquier unidad de trabajo abierta, porque
        # preguntar por el diferencial vuelve a entrar en estas mismas —el puerto
        # se apoya en las estadísticas del jugador, que consultan quick_match y
        # golf_course— y anidar dos `async with` sobre la misma sesión la
        # cerraría antes de tiempo
        eventos: list[ActivityEvent] = []
        for vuelta in vueltas:
            contexto = record_context(
                await self._differentials.round_differentials(vuelta.user_id),
                lambda r: r.source_id == quick_match_id_raw,
            )
            logros = self._detector.detect(holes=vuelta.holes, context=contexto)
            eventos.extend(
                self._a_eventos(
                    logros,
                    vuelta.user_id,
                    vuelta.match_id,
                    vuelta.golf_course_id,
                    vuelta.occurred_at,
                    len(vuelta.holes),
                    vuelta.visible_to_friends,
                )
            )

        eventos.extend(await self._campo_nuevo(quick_match_id_raw, visibles))
        if not eventos:
            return 0

        # Fase 3: publicar
        # Una fecha para toda la publicacion y el interruptor de ahora mismo
        eventos = await stamp_for_publication(self._user_uow, eventos, published_at)
        async with self._social_uow:
            repo = self._social_uow.activity_events
            await lock_players(repo, [e.user_id for e in eventos if e.type in EXCLUSIVE_TYPES])
            eventos = await keep_only_the_oldest(
                repo, eventos, is_own=lambda e: e.source_match_id == quick_match_id_raw
            )
            await repo.add_many(eventos)

        return len(eventos)

    async def republish_new_course(self, quick_match_id_raw: str) -> int:
        """Vuelve a publicar solo su «campo nuevo»: hereda el de un torneo reabierto."""
        return await self.execute(quick_match_id_raw, only_new_course=True)

    async def _campo_nuevo(
        self, quick_match_id_raw: str, visibles: dict[UserId, bool]
    ) -> list[ActivityEvent]:
        """
        El «campo nuevo» de quien piso el campo por primera vez en esta partida,
        segun el historial: el mismo criterio que los torneos (al menos un
        hoyo), asi que vale tambien una tarjeta incompleta.
        """
        if not visibles:
            return []
        rondas = await self._history.played_rounds(list(visibles))
        return [
            ActivityEvent.create(
                user_id=user_id,
                type=ActivityEventType.NEW_COURSE,
                occurred_at=primera.instant,
                source_match_id=primera.source_id,
                payload={
                    "golf_course_id": primera.golf_course_id,
                    "holes_played": primera.holes_played,
                    PLAYED_AT: as_iso(primera.instant),
                },
                visible_to_friends=visibles[user_id],
            )
            for (user_id, _), primera in first_on_each_course(rondas).items()
            if primera.source_id == quick_match_id_raw and user_id in visibles
        ]

    async def _leer_vueltas(
        self, quick_match_id_raw: str
    ) -> tuple[list["_RoundToJudge"], dict[UserId, bool]]:
        """
        Las vueltas computables de la partida, ya reducidas a lo que hay que
        juzgar, y si cada participante con cuenta publica para sus amigos.

        Deja resuelto aquí todo lo que necesita base de datos —quién publica, qué
        hoyos cuentan, quién estrena campo— para que juzgar no tenga que volver.
        """
        async with self._quick_match_uow, self._golf_course_uow, self._user_uow:
            match = await self._quick_match_uow.quick_matches.find_by_id(
                QuickMatchId(quick_match_id_raw)
            )
            if match is None or match.status != QuickMatchStatus.COMPLETED:
                return [], {}

            course = await self._golf_course_uow.golf_courses.find_by_id(match.golf_course_id)
            if course is None:
                return [], {}

            scores = await self._quick_match_uow.quick_match_hole_scores.find_by_match(match.id)

            vueltas: list[_RoundToJudge] = []
            visibles: dict[UserId, bool] = {}
            for participant in match.participants:
                if participant.is_guest or participant.user_id is None:
                    continue

                # Con la publicacion apagada tambien se publica, pero solo para
                # el: el interruptor decide lo que ven los demas, no lo que ve
                # uno de si mismo
                user = await self._user_uow.users.find_by_id(participant.user_id)
                if user is None:
                    continue
                visibles[participant.user_id] = user.share_activity

                scores_by_hole = {
                    score.hole_number: score.score
                    for score in scores
                    if score.participant_id == participant.participant_id
                }
                # El par y el índice son de la barra que juega: un birdie se
                # mide contra el par de su tarjeta, no contra el del campo
                jugados = countable_holes(
                    scores_by_hole,
                    course.hole_card_for(participant.tee_color, participant.tee_gender),
                )
                if jugados is None:
                    # Tarjeta incompleta: si no vale para la media, no vale para
                    # presumir (BE #173). Su «campo nuevo» si, que lo decide
                    # el historial
                    continue

                vueltas.append(
                    _RoundToJudge(
                        user_id=participant.user_id,
                        match_id=str(match.id.value),
                        golf_course_id=str(match.golf_course_id.value),
                        occurred_at=utc_naive(match.played_at),
                        visible_to_friends=user.share_activity,
                        holes=[
                            # La raya (score nulo: el jugador recogio) es un
                            # hoyo jugado, juzgado como doble bogey: no inventa
                            # ningun logro, y el birdie de otro hoyo de la
                            # misma vuelta se sigue pudiendo presumir
                            PlayedHole.of(hole.number, hole.par, scores_by_hole[hole.number])
                            for hole in jugados
                        ],
                    )
                )

        return vueltas, visibles

    def _a_eventos(
        self,
        logros: list[DetectedAchievement],
        user_id: UserId,
        match_id: str,
        golf_course_id: str,
        occurred_at: datetime,
        holes_played: int,
        visible_to_friends: bool,
    ) -> list[ActivityEvent]:
        """Convierte los logros detectados en entradas del feed."""
        return [
            ActivityEvent.create(
                user_id=user_id,
                type=logro.type,
                occurred_at=occurred_at,
                source_match_id=match_id,
                payload=self._payload(logro, golf_course_id, holes_played),
                visible_to_friends=visible_to_friends,
            )
            for logro in logros
        ]

    @staticmethod
    def _payload(logro: DetectedAchievement, golf_course_id: str, holes_played: int) -> dict:
        """
        El detalle propio de cada tipo, para que el feed no tenga que ir a
        buscarlo a otras tablas al pintar la entrada.
        """
        payload: dict = {
            "golf_course_id": golf_course_id,
            "holes_played": holes_played,
        }
        if logro.count > 1:
            payload["count"] = logro.count
        if logro.holes:
            payload["holes"] = list(logro.holes)
        if logro.detail:
            payload.update(logro.detail)
        return payload
