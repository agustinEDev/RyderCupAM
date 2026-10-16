"""
Quién aportó hace poco una muestra de hoyo, en la memoria del proceso (BE #532).

Una entrada por jugador, campo, hoyo y barra, que caduca a los 10 minutos. Nada
de esto va a la base de datos ni a los logs, y con un tope de entradas: si se
llena, se olvidan antes las más viejas (lo peor que pasa es que alguien aporte
una muestra más pronto).

Con varios procesos cada uno lleva su cuenta, y al reiniciar se olvida todo: es
un freno contra el que manda de más, no una garantía.
"""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable

from src.modules.golf_course.application.ports.recent_hole_sample_senders import (
    IRecentHoleSampleSenders,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender

WINDOW_SECONDS = 600.0
MAX_ENTRIES = 50_000

_Key = tuple[str, str, int, str, str | None]


class InMemoryRecentHoleSampleSenders(IRecentHoleSampleSenders):
    """Diccionario ordenado por llegada, con caducidad y tamaño acotado."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        window_seconds: float = WINDOW_SECONDS,
        max_entries: int = MAX_ENTRIES,
    ) -> None:
        self._clock = clock
        self._window = window_seconds
        self._max_entries = max_entries
        self._recorded_at: OrderedDict[_Key, float] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _key(
        user_id: str,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee_color: TeeColor,
        tee_gender: Gender | None,
    ) -> _Key:
        gender = None if tee_gender is None else tee_gender.value
        return (user_id, str(golf_course_id), hole_number, tee_color.value, gender)

    def _forget_expired(self, now: float) -> None:
        # Ordenado por llegada: las caducadas están todas al principio
        while self._recorded_at:
            key, at = next(iter(self._recorded_at.items()))
            if now - at < self._window:
                return
            del self._recorded_at[key]

    def allowed(
        self,
        user_id: str,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee_color: TeeColor,
        tee_gender: Gender | None,
    ) -> bool:
        with self._lock:
            self._forget_expired(self._clock())
            key = self._key(user_id, golf_course_id, hole_number, tee_color, tee_gender)
            return key not in self._recorded_at

    def record(
        self,
        user_id: str,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee_color: TeeColor,
        tee_gender: Gender | None,
    ) -> None:
        with self._lock:
            now = self._clock()
            self._forget_expired(now)
            key = self._key(user_id, golf_course_id, hole_number, tee_color, tee_gender)
            self._recorded_at.pop(key, None)  # Al final: es la más reciente
            self._recorded_at[key] = now
            while len(self._recorded_at) > self._max_entries:
                self._recorded_at.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._recorded_at)
