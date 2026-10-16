"""
Tests de quién mandó hace poco una muestra de hoyo, en memoria (BE #532, 16 oct 2026).

Una por jugador, campo, hoyo y barra (color y género) cada 10 minutos. Vive
solo en la memoria del proceso, con caducidad y un tope de entradas: nunca llega
a la BD ni a los logs.

| Caso                                     | Resultado                                   |
|------------------------------------------|---------------------------------------------|
| Sin nada apuntado                        | Permitido                                   |
| Apuntado hace 599 s                      | No permitido                                |
| Apuntado hace 600 s                      | Permitido (y la entrada se va)              |
| Otro jugador, otro hoyo, otro campo      | Permitido                                   |
| Otra barra (color, género o sin género)  | Permitido                                   |
| Volver a apuntar                         | La ventana empieza de nuevo                 |
| Más entradas que el tope                 | Se olvidan las más viejas; nunca pasa del tope |
"""

from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.services.in_memory_recent_hole_sample_senders import (
    WINDOW_SECONDS,
    InMemoryRecentHoleSampleSenders,
)
from src.shared.domain.value_objects.gender import Gender

AMARILLAS = (TeeColor.YELLOW, Gender.MALE)
CAMPO = GolfCourseId.generate()
OTRO_CAMPO = GolfCourseId.generate()


class Reloj:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _senders(max_entries: int = 1000):
    reloj = Reloj()
    return InMemoryRecentHoleSampleSenders(clock=reloj, max_entries=max_entries), reloj


def test_the_window_is_ten_minutes():
    """
    GIVEN: La regla del 16 oct
    WHEN: Se mira la ventana
    THEN: 600 segundos
    """
    assert WINDOW_SECONDS == 600


def test_nothing_recorded_is_allowed():
    """
    GIVEN: Nada apuntado
    WHEN: Se pregunta por un jugador
    THEN: Permitido
    """
    senders, _ = _senders()

    assert senders.allowed("u1", CAMPO, 1, *AMARILLAS) is True


def test_within_the_window_is_not_allowed():
    """
    GIVEN: Una muestra apuntada del jugador en el hoyo 1
    WHEN: Se pregunta a los 599 s
    THEN: No permitido
    """
    senders, reloj = _senders()
    senders.record("u1", CAMPO, 1, *AMARILLAS)
    reloj.now += 599

    assert senders.allowed("u1", CAMPO, 1, *AMARILLAS) is False


def test_after_the_window_is_allowed_and_forgotten():
    """
    GIVEN: Una muestra apuntada del jugador en el hoyo 1
    WHEN: Se pregunta a los 600 s
    THEN: Permitido, y la entrada ya no está
    """
    senders, reloj = _senders()
    senders.record("u1", CAMPO, 1, *AMARILLAS)
    reloj.now += 600

    assert senders.allowed("u1", CAMPO, 1, *AMARILLAS) is True
    assert len(senders) == 0


def test_other_player_hole_or_course_is_allowed():
    """
    GIVEN: Una muestra apuntada del jugador u1 en el hoyo 1 del campo
    WHEN: Se pregunta por u2, por el hoyo 2 y por otro campo
    THEN: Permitido en los tres
    """
    senders, _ = _senders()
    senders.record("u1", CAMPO, 1, *AMARILLAS)

    assert senders.allowed("u2", CAMPO, 1, *AMARILLAS) is True
    assert senders.allowed("u1", CAMPO, 2, *AMARILLAS) is True
    assert senders.allowed("u1", OTRO_CAMPO, 1, *AMARILLAS) is True


def test_recording_again_restarts_the_window():
    """
    GIVEN: Una apuntada, y otra del mismo jugador y hoyo a los 600 s
    WHEN: Se pregunta a los 900 s
    THEN: No permitido: cuenta desde la segunda
    """
    senders, reloj = _senders()
    senders.record("u1", CAMPO, 1, *AMARILLAS)
    reloj.now += 600
    senders.record("u1", CAMPO, 1, *AMARILLAS)
    reloj.now += 300

    assert senders.allowed("u1", CAMPO, 1, *AMARILLAS) is False


def test_the_size_is_bounded_and_the_oldest_go_first():
    """
    GIVEN: Un tope de 3 entradas
    WHEN: Se apuntan 5 jugadores, uno por segundo
    THEN: Quedan 3: los dos primeros se olvidan (vuelven a poder) y los últimos no
    """
    senders, reloj = _senders(max_entries=3)
    for i in range(5):
        senders.record(f"u{i}", CAMPO, 1, *AMARILLAS)
        reloj.now += 1

    assert len(senders) == 3
    assert senders.allowed("u0", CAMPO, 1, *AMARILLAS) is True
    assert senders.allowed("u1", CAMPO, 1, *AMARILLAS) is True
    assert senders.allowed("u4", CAMPO, 1, *AMARILLAS) is False


def test_other_tee_is_allowed():
    """
    GIVEN: Una muestra apuntada del jugador en el hoyo 1 desde amarillas de hombre
    WHEN: Se pregunta por rojas de hombre, amarillas de mujer y amarillas sin género
    THEN: Permitido en las tres
    """
    senders, _ = _senders()
    senders.record("u1", CAMPO, 1, *AMARILLAS)

    assert senders.allowed("u1", CAMPO, 1, TeeColor.RED, Gender.MALE) is True
    assert senders.allowed("u1", CAMPO, 1, TeeColor.YELLOW, Gender.FEMALE) is True
    assert senders.allowed("u1", CAMPO, 1, TeeColor.YELLOW, None) is True
