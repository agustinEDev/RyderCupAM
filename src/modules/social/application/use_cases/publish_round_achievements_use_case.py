"""Caso de Uso: Publicar en el feed los logros de una vuelta terminada."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.social.application.ports.player_course_history_interface import (
    PlayerCourseHistoryInterface,
)
from src.modules.social.application.ports.player_differentials_interface import (
    PlayerDifferentialsInterface,
)
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
        best_differential_before: dict[str, float | None] | None = None,
    ) -> int:
        """
        Publica lo que merezca publicarse y devuelve cuántos eventos creó.

        `best_differential_before` lleva, por jugador, su mejor diferencial
        **antes** de que esta vuelta contara. Lo captura quien cierra la partida,
        porque una vez cerrada ya no hay forma de preguntarlo: las estadísticas
        solo miran partidas terminadas y esta ya lo está. Comparando aquel valor
        con el de ahora se sabe si la vuelta batió el récord, sin recalcular por
        segunda vez un diferencial que el módulo de estadísticas ya sabe hacer.
        """
        best_before = best_differential_before or {}

        # Fase 1: leer. Todo lo que hace falta de la partida, en un solo paso y
        # con las unidades de trabajo abiertas lo justo
        vueltas = await self._leer_vueltas(quick_match_id_raw)
        if not vueltas:
            return 0

        # Fase 2: juzgar. Fuera de cualquier unidad de trabajo abierta, porque
        # preguntar por el diferencial vuelve a entrar en estas mismas —el puerto
        # se apoya en las estadísticas del jugador, que consultan quick_match y
        # golf_course— y anidar dos `async with` sobre la misma sesión la
        # cerraría antes de tiempo
        eventos: list[ActivityEvent] = []
        for vuelta in vueltas:
            contexto = RoundContext(
                is_first_round_on_course=not await self._history.has_played_course_before(
                    vuelta.user_id, vuelta.golf_course_id, vuelta.match_id
                ),
                # Esto es una partida rápida: estrenar torneo se publica desde
                # el cierre de la competición
                is_first_tournament=False,
                previous_best_differential=self._como_decimal(
                    best_before.get(str(vuelta.user_id.value))
                ),
                differential=await self._diferencial_si_es_record(
                    vuelta.user_id, best_before.get(str(vuelta.user_id.value))
                ),
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
                )
            )

        if not eventos:
            return 0

        # Fase 3: publicar
        async with self._social_uow:
            await self._social_uow.activity_events.add_many(eventos)

        return len(eventos)

    async def _leer_vueltas(self, quick_match_id_raw: str) -> list["_RoundToJudge"]:
        """
        Las vueltas publicables de la partida, ya reducidas a lo que hay que
        juzgar.

        Deja resuelto aquí todo lo que necesita base de datos —quién publica, qué
        hoyos cuentan, quién estrena campo— para que juzgar no tenga que volver.
        """
        async with self._quick_match_uow, self._golf_course_uow, self._user_uow:
            match = await self._quick_match_uow.quick_matches.find_by_id(
                QuickMatchId(quick_match_id_raw)
            )
            if match is None or match.status != QuickMatchStatus.COMPLETED:
                return []

            course = await self._golf_course_uow.golf_courses.find_by_id(match.golf_course_id)
            if course is None:
                return []

            scores = await self._quick_match_uow.quick_match_hole_scores.find_by_match(match.id)

            vueltas: list[_RoundToJudge] = []
            for participant in match.participants:
                if participant.is_guest or participant.user_id is None:
                    continue

                user = await self._user_uow.users.find_by_id(participant.user_id)
                if user is None or not user.share_activity:
                    continue

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
                    # presumir (BE #173)
                    continue

                vueltas.append(
                    _RoundToJudge(
                        user_id=participant.user_id,
                        match_id=str(match.id.value),
                        golf_course_id=str(match.golf_course_id.value),
                        occurred_at=match.created_at,
                        holes=[
                            PlayedHole(
                                number=hole.number,
                                par=hole.par,
                                strokes=scores_by_hole[hole.number],
                            )
                            for hole in jugados
                        ],
                    )
                )

        return vueltas

    async def _diferencial_si_es_record(
        self, user_id: UserId, best_before: float | None
    ) -> Decimal | None:
        """
        El diferencial de esta vuelta, pero solo cuando ha batido el récord.

        No se recalcula: si el mejor diferencial del jugador ha mejorado desde
        que se cerró la partida, la única vuelta nueva es esta, así que el nuevo
        mejor **es** el suyo. Cuando no ha mejorado se devuelve None y el
        detector no publica récord, que es justo lo que debe pasar.

        Devolver None cuando no hay nada con lo que comparar deja fuera la
        primera vuelta con diferencial: es el punto de partida, no un récord.
        """
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
        user_id: UserId,
        match_id: str,
        golf_course_id: str,
        occurred_at: datetime,
        holes_played: int,
    ) -> list[ActivityEvent]:
        """Convierte los logros detectados en entradas del feed."""
        return [
            ActivityEvent.create(
                user_id=user_id,
                type=logro.type,
                # La partida rápida no guarda cuándo se jugó: se crea el mismo
                # día, igual que asumen las estadísticas
                occurred_at=occurred_at,
                source_match_id=match_id,
                payload=self._payload(logro, golf_course_id, holes_played),
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
