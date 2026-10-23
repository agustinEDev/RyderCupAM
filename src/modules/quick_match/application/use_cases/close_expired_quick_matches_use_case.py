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
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
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
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus

logger = logging.getLogger(__name__)


def ahora_en_utc() -> datetime:
    """El reloj del cierre: ahora, en UTC sin zona como las fechas guardadas."""
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
        reloj: Callable[[], datetime] = ahora_en_utc,
    ):
        self._uow = uow
        self._golf_course_uow = golf_course_uow
        self._achievements = achievements
        self._reloj = reloj

    async def execute(self) -> ClosedQuickMatches:
        ahora = self._reloj()
        async with self._uow:
            # Valores sueltos y no las entidades: si una partida falla, el
            # rollback caduca todo lo cargado en la sesión, y leerlo después
            # reventaba la vuelta entera
            abiertas = [_Abierta.de(p) for p in await self._uow.quick_matches.list_open()]
        if not abiertas:
            return ClosedQuickMatches()
        zonas = await self._zonas(abiertas)

        completed = cancelled = published = 0
        for abierta in abiertas:
            zona = zonas.get(abierta.golf_course_id)
            try:
                if not _vencida(abierta, zona, ahora):
                    continue
                cerrada = await self._cierra(abierta.id, zona, ahora)
            except Exception:
                logger.exception("Could not close quick match %s", abierta.id)
                continue
            if cerrada is None:
                continue
            estado, plazo = cerrada
            if estado == QuickMatchStatus.CANCELLED:
                cancelled += 1
                continue
            completed += 1
            if publishes_when_closed(plazo, ahora) and await self._publica(abierta.id):
                published += 1
        return ClosedQuickMatches(completed, cancelled, published)

    async def _zonas(self, abiertas: list["_Abierta"]) -> dict:
        """La zona horaria de cada campo; sin campo (borrado) no hay, y se usa UTC."""
        ids = list({a.golf_course_id for a in abiertas})
        async with self._golf_course_uow:
            campos = await self._golf_course_uow.golf_courses.find_by_ids(ids)
        return {campo.id: campo.timezone for campo in campos}

    async def _cierra(
        self, quick_match_id: QuickMatchId, zona: str | None, ahora: datetime
    ) -> tuple[QuickMatchStatus, datetime] | None:
        """
        La cierra si sigue abierta y vencida; devuelve cómo queda y su plazo, o
        None si no la tocó. El plazo se vuelve a mirar con la fila bloqueada:
        leída PENDING y vencida, puede haberla empezado el creador entretanto.
        """
        async with self._uow:
            actual = await self._uow.quick_matches.find_by_id_for_update(quick_match_id)
            if actual is None:
                return None
            plazo = _plazo(_Abierta.de(actual), zona)
            if plazo is None or ahora < plazo:
                return None
            con_golpes = actual.status.is_in_progress() and bool(
                await self._uow.quick_match_hole_scores.find_by_match(actual.id)
            )
            if con_golpes:
                actual.complete()
            else:
                actual.cancel()
            await self._uow.quick_matches.update(actual)
            return actual.status, plazo

    async def _publica(self, quick_match_id: QuickMatchId) -> bool:
        """
        Sus logros y su resultado en Actividad, sin que un fallo tumbe el cierre.
        Cuenta si publicó algo: el publicador se traga sus propios fallos.
        """
        if self._achievements is None:
            return False
        try:
            return await self._achievements.publish(str(quick_match_id.value)) > 0
        except Exception:
            logger.warning(
                "Could not publish quick match %s closed on its own", quick_match_id, exc_info=True
            )
            return False


@dataclass(frozen=True)
class _Abierta:
    """Lo que hace falta de una partida abierta para saber si vence."""

    id: QuickMatchId
    status: QuickMatchStatus
    created_at: datetime
    started_at: datetime | None
    golf_course_id: GolfCourseId

    @classmethod
    def de(cls, partida: QuickMatch) -> "_Abierta":
        return cls(
            partida.id,
            partida.status,
            partida.created_at,
            partida.started_at,
            partida.golf_course_id,
        )


def _plazo(abierta: _Abierta, zona: str | None) -> datetime | None:
    return closes_at(
        status=abierta.status,
        created_at=abierta.created_at,
        started_at=abierta.started_at,
        timezone=zona,
    )


def _vencida(abierta: _Abierta, zona: str | None, ahora: datetime) -> bool:
    plazo = _plazo(abierta, zona)
    return plazo is not None and ahora >= plazo
