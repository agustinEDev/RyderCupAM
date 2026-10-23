"""
Domain Service: AchievementDetector.

Decide qué merece publicarse de una vuelta ya terminada. Puro, sin IO.

Aquí vive la única regla que gobierna el feed: **se publican logros, no
actividad**. Nada de lo que salga de aquí puede delatar una vuelta mala, porque
un feed que publica los días malos empuja a no anotarlos, y las tarjetas sin
terminar ya sesgan las estadísticas de por sí (BE #173).

«Campo nuevo» y «primer torneo» no salen de aquí: dependen de todo lo que el
jugador ha jugado, no de esta vuelta (`exclusive_achievements`, 22 oct 2026).
"""

from dataclasses import dataclass
from decimal import Decimal

from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType

# Golpes bajo par que definen cada logro por hoyo
BIRDIE_UNDER_PAR = 1
EAGLE_UNDER_PAR = 2
HOLE_IN_ONE_STROKES = 1


# Golpes sobre el par con los que se juzga un hoyo que no se termino (la raya):
# doble bogey, sin golpes recibidos. En los totales la raya vale su doble bogey
# NETO (`par + 2 + golpes recibidos`, Agustin, 23 oct 2026), pero aqui da igual:
# el detector solo busca birdies o mejor hoyo a hoyo, y una raya no lo es con
# ningun reparto realista
PICKED_UP_OVER_PAR = 2


@dataclass(frozen=True)
class PlayedHole:
    """Un hoyo jugado, con lo justo para juzgarlo."""

    number: int
    par: int
    strokes: int

    @classmethod
    def of(cls, number: int, par: int, strokes: int | None) -> "PlayedHole":
        """El hoyo con sus golpes, o la raya (None) juzgada como doble bogey."""
        return cls(number, par, par + PICKED_UP_OVER_PAR if strokes is None else strokes)


@dataclass(frozen=True)
class RoundContext:
    """
    Lo que hay que saber del pasado del jugador para juzgar esta vuelta.

    Se pasa ya resuelto en lugar de dejar que el detector consulte nada: así
    sigue siendo puro y se puede probar sin base de datos.
    """

    previous_best_differential: Decimal | None = None
    differential: Decimal | None = None


@dataclass(frozen=True)
class DetectedAchievement:
    """
    Un logro listo para publicarse.

    `count` agrupa los de un mismo tipo dentro de la vuelta: cuatro birdies son
    una entrada que dice cuatro, no cuatro entradas seguidas empujándose unas a
    otras en el feed de los amigos.
    """

    type: ActivityEventType
    count: int = 1
    holes: tuple[int, ...] = ()
    detail: dict | None = None


class AchievementDetector:
    """Qué merece contarse de una vuelta."""

    def detect(
        self, holes: list[PlayedHole], context: RoundContext | None = None
    ) -> list[DetectedAchievement]:
        """
        Los logros de una vuelta, agrupados y sin solaparse entre sí.

        Cada hoyo aporta **como mucho un logro, el mayor**: un hoyo en uno en un
        par 4 es también un albatros y un eagle, pero contarlo tres veces sería
        absurdo. El orden de preferencia es hoyo en uno, luego eagle o mejor, y
        por último birdie.
        """
        context = context or RoundContext()
        achievements: list[DetectedAchievement] = []

        por_tipo: dict[ActivityEventType, list[int]] = {}
        for hole in holes:
            tipo = self._hole_achievement(hole)
            if tipo is not None:
                por_tipo.setdefault(tipo, []).append(hole.number)

        # Del más raro al más común, que es como se leen en el feed
        for tipo in (
            ActivityEventType.HOLE_IN_ONE,
            ActivityEventType.EAGLE_OR_BETTER,
            ActivityEventType.BIRDIE,
        ):
            numeros = por_tipo.get(tipo)
            if numeros:
                achievements.append(
                    DetectedAchievement(type=tipo, count=len(numeros), holes=tuple(numeros))
                )

        achievements.extend(self._round_achievements(context))
        return achievements

    @staticmethod
    def _hole_achievement(hole: PlayedHole) -> ActivityEventType | None:
        """El mayor logro de un hoyo, o None si no hubo ninguno."""
        if hole.strokes <= 0 or hole.par <= 0:
            return None

        if hole.strokes == HOLE_IN_ONE_STROKES:
            # Un hoyo en uno en un par 3 es además un eagle; se cuenta una vez
            return ActivityEventType.HOLE_IN_ONE

        under_par = hole.par - hole.strokes
        if under_par >= EAGLE_UNDER_PAR:
            return ActivityEventType.EAGLE_OR_BETTER
        if under_par == BIRDIE_UNDER_PAR:
            return ActivityEventType.BIRDIE
        return None

    @staticmethod
    def _round_achievements(context: RoundContext) -> list[DetectedAchievement]:
        """Los logros que dependen del pasado del jugador, no de un hoyo."""
        achievements: list[DetectedAchievement] = []

        # Récord personal: hace falta un diferencial que batir y uno anterior con
        # el que compararlo. La primera vuelta con diferencial no es un récord,
        # es el punto de partida — anunciarla como récord sería vacío
        if (
            context.differential is not None
            and context.previous_best_differential is not None
            and context.differential < context.previous_best_differential
        ):
            achievements.append(
                DetectedAchievement(
                    type=ActivityEventType.PERSONAL_BEST,
                    detail={
                        "differential": str(context.differential),
                        "previous_best": str(context.previous_best_differential),
                    },
                )
            )

        return achievements
