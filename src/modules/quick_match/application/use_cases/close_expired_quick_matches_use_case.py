"""
Caso de Uso: Cerrar las partidas rápidas que nadie termina (Agustín, 23 oct 2026).

Lo lanza un proceso periódico, no una petición. Cada partida pasado su plazo
(`quick_match_closing`):

- En juego con algún golpe (una raya también) -> COMPLETED con lo anotado,
  como si la finalizara el creador: se publican sus logros y su resultado,
  salvo que se cierre más de 2 días tarde.
- En juego sin ningún golpe, o sin empezar -> CANCELLED: no hay nada que contar.

Cada partida se cierra en su propia transacción y bloqueada, mirando otra vez
su estado: si el creador la terminó mientras tanto, no se toca. Un fallo en una
no para las demás.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.quick_match.application.ports.round_achievements_publisher_interface import (
    RoundAchievementsPublisherInterface,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.services.quick_match_closing import (
    closes_at,
    publishes_when_closed,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus

logger = logging.getLogger(__name__)


def _ahora() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class ClosedQuickMatches:
    """Lo que hizo una pasada."""

    completed: int = 0
    cancelled: int = 0
    published: int = 0


class CloseExpiredQuickMatchesUseCase:
    """Cierra las partidas rápidas abiertas cuyo plazo ya pasó."""

    def __init__(
        self,
        uow: QuickMatchUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
        achievements: RoundAchievementsPublisherInterface | None = None,
        reloj: Callable[[], datetime] = _ahora,
    ):
        self._uow = uow
        self._golf_course_uow = golf_course_uow
        self._achievements = achievements
        self._reloj = reloj

    async def execute(self) -> ClosedQuickMatches:
        ahora = self._reloj()
        async with self._uow:
            abiertas = await self._uow.quick_matches.list_open()
        if not abiertas:
            return ClosedQuickMatches()
        zonas = await self._zonas(abiertas)

        completed = cancelled = published = 0
        for partida in abiertas:
            plazo = closes_at(
                status=partida.status,
                created_at=partida.created_at,
                started_at=partida.started_at,
                timezone=zonas.get(partida.golf_course_id),
            )
            if plazo is None or ahora < plazo:
                continue
            try:
                estado = await self._cierra(partida)
            except Exception:
                logger.exception("Could not close quick match %s", partida.id)
                continue
            if estado == QuickMatchStatus.CANCELLED:
                cancelled += 1
            elif estado == QuickMatchStatus.COMPLETED:
                completed += 1
                if publishes_when_closed(plazo, ahora) and await self._publica(partida):
                    published += 1
        return ClosedQuickMatches(completed, cancelled, published)

    async def _zonas(self, partidas: list[QuickMatch]) -> dict:
        """La zona horaria de cada campo; sin campo (borrado) no hay, y se usa UTC."""
        ids = list({p.golf_course_id for p in partidas})
        async with self._golf_course_uow:
            campos = await self._golf_course_uow.golf_courses.find_by_ids(ids)
        return {campo.id: campo.timezone for campo in campos}

    async def _cierra(self, partida: QuickMatch) -> QuickMatchStatus | None:
        """La cierra si sigue abierta; devuelve cómo queda, o None si no la tocó."""
        async with self._uow:
            actual = await self._uow.quick_matches.find_by_id_for_update(partida.id)
            if actual is None or actual.status.is_final():
                return None
            con_golpes = actual.status.is_in_progress() and bool(
                await self._uow.quick_match_hole_scores.find_by_match(actual.id)
            )
            if con_golpes:
                actual.complete()
            else:
                actual.cancel()
            await self._uow.quick_matches.update(actual)
            return actual.status

    async def _publica(self, partida: QuickMatch) -> bool:
        """Sus logros y su resultado en Actividad, sin que un fallo tumbe el cierre."""
        if self._achievements is None:
            return False
        try:
            await self._achievements.publish(str(partida.id.value))
        except Exception:
            logger.warning(
                "Could not publish quick match %s closed on its own", partida.id, exc_info=True
            )
            return False
        return True
