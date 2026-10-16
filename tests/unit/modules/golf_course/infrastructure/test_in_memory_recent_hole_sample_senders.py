"""
Tests de quién aportó hace poco una muestra de hoyo, en memoria (BE #532, 16 oct 2026).

Una por jugador, campo, hoyo y barra (color y género) cada 10 minutos. Vive
solo en la memoria del proceso, con caducidad y un tope de entradas: nunca llega
a la BD ni a los logs. Mirar y apartar el hueco es una sola operación
(`reserve`), para que dos peticiones a la vez del mismo jugador no pasen las
dos; luego se confirma (la muestra se guardó) o se suelta (no se guardó).

| Caso                                     | Resultado                                   |
|------------------------------------------|---------------------------------------------|
| Sin nada apuntado                        | Se reserva                                  |
| Reservado y sin confirmar ni soltar      | Una segunda reserva no entra                |
| Reservado y soltado                      | Se vuelve a poder reservar                  |
| Confirmado hace 599 s                    | No se reserva                               |
| Confirmado hace 600 s                    | Se reserva (y la entrada se va)             |
| Otro jugador, otro hoyo, otro campo      | Se reserva                                  |
| Otra barra (color, género o sin género)  | Se reserva                                  |
| Volver a confirmar                       | La ventana empieza de nuevo                 |
| Más confirmadas que el tope              | Se olvidan las más viejas; nunca pasa del tope |
| Ocho hilos a la vez                      | Solo uno reserva                            |
"""

import threading

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


def _key(user="u1", course=CAMPO, hole=1, tee=AMARILLAS):
    return (user, course, hole, *tee)


def _accepted(senders, key=None) -> None:
    """Una muestra aceptada: se reserva y se confirma."""
    key = key or _key()
    assert senders.reserve(*key) is True
    senders.confirm(*key)


def test_the_window_is_ten_minutes():
    """
    GIVEN: La regla del 16 oct
    WHEN: Se mira la ventana
    THEN: 600 segundos
    """
    assert WINDOW_SECONDS == 600


def test_nothing_recorded_can_be_reserved():
    """
    GIVEN: Nada apuntado
    WHEN: Se reserva para un jugador
    THEN: Entra
    """
    senders, _ = _senders()

    assert senders.reserve(*_key()) is True


def test_a_pending_reservation_blocks_a_second_one():
    """
    GIVEN: Una reserva del jugador sin confirmar ni soltar (su petición sigue en curso)
    WHEN: Llega otra petición suya a la misma barra
    THEN: No entra
    """
    senders, _ = _senders()
    senders.reserve(*_key())

    assert senders.reserve(*_key()) is False


def test_a_released_reservation_frees_the_slot():
    """
    GIVEN: Una reserva soltada (la muestra no se guardó)
    WHEN: Se vuelve a reservar
    THEN: Entra, y no queda nada apuntado
    """
    senders, _ = _senders()
    senders.reserve(*_key())
    senders.release(*_key())

    assert len(senders) == 0
    assert senders.reserve(*_key()) is True


def test_within_the_window_cannot_reserve():
    """
    GIVEN: Una muestra aceptada del jugador en el hoyo 1
    WHEN: Se reserva a los 599 s
    THEN: No entra
    """
    senders, reloj = _senders()
    _accepted(senders)
    reloj.now += 599

    assert senders.reserve(*_key()) is False


def test_after_the_window_can_reserve_and_is_forgotten():
    """
    GIVEN: Una muestra aceptada del jugador en el hoyo 1
    WHEN: Se mira a los 600 s
    THEN: La entrada ya no está, y se puede reservar
    """
    senders, reloj = _senders()
    _accepted(senders)
    reloj.now += 600

    assert senders.reserve(*_key()) is True
    senders.release(*_key())
    assert len(senders) == 0


def test_other_player_hole_or_course_can_reserve():
    """
    GIVEN: Una muestra aceptada de u1 en el hoyo 1 del campo
    WHEN: Se reserva para u2, para el hoyo 2 y para otro campo
    THEN: Entran las tres
    """
    senders, _ = _senders()
    _accepted(senders)

    assert senders.reserve(*_key(user="u2")) is True
    assert senders.reserve(*_key(hole=2)) is True
    assert senders.reserve(*_key(course=OTRO_CAMPO)) is True


def test_other_tee_can_reserve():
    """
    GIVEN: Una muestra aceptada de u1 en el hoyo 1 desde amarillas de hombre
    WHEN: Se reserva desde rojas de hombre, amarillas de mujer y amarillas sin género
    THEN: Entran las tres
    """
    senders, _ = _senders()
    _accepted(senders)

    assert senders.reserve(*_key(tee=(TeeColor.RED, Gender.MALE))) is True
    assert senders.reserve(*_key(tee=(TeeColor.YELLOW, Gender.FEMALE))) is True
    assert senders.reserve(*_key(tee=(TeeColor.YELLOW, None))) is True


def test_confirming_again_restarts_the_window():
    """
    GIVEN: Una aceptada, y otra del mismo jugador y barra a los 600 s
    WHEN: Se reserva a los 900 s
    THEN: No entra: cuenta desde la segunda
    """
    senders, reloj = _senders()
    _accepted(senders)
    reloj.now += 600
    _accepted(senders)
    reloj.now += 300

    assert senders.reserve(*_key()) is False


def test_the_size_is_bounded_and_the_oldest_go_first():
    """
    GIVEN: Un tope de 3 entradas
    WHEN: Se aceptan muestras de 5 jugadores, uno por segundo
    THEN: Quedan 3: los dos primeros se olvidan (vuelven a poder) y los últimos no
    """
    senders, reloj = _senders(max_entries=3)
    for i in range(5):
        _accepted(senders, _key(user=f"u{i}"))
        reloj.now += 1

    assert len(senders) == 3
    assert senders.reserve(*_key(user="u0")) is True
    assert senders.reserve(*_key(user="u1")) is True
    assert senders.reserve(*_key(user="u4")) is False


def test_eight_threads_at_once_reserve_once():
    """
    GIVEN: Ocho hilos que reservan a la vez la misma barra del mismo jugador
    WHEN: Arrancan juntos
    THEN: Solo uno entra
    """
    senders, _ = _senders()
    start = threading.Barrier(8)
    results: list[bool] = []

    def reserve() -> None:
        start.wait()
        results.append(senders.reserve(*_key()))

    threads = [threading.Thread(target=reserve) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == [False] * 7 + [True]
