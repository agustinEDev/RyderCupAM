"""
El cableado de Actividad (revision final de bugs, 22 oct 2026): el publicador
de `competition` lleva el caso de uso de logros de torneo, para volver a
publicar los torneos del mismo dia al reabrir o cancelar uno; y borrar una
ronda avisa a Actividad.
"""

from types import SimpleNamespace

from src.config.dependencies import (
    get_competition_activity_publisher,
    get_configure_schedule_use_case,
    get_delete_round_use_case,
)


def test_the_activity_publisher_carries_the_tournament_achievements():
    logros = object()
    uows = SimpleNamespace(competition=object(), user=SimpleNamespace(users=object()))

    publicador = get_competition_activity_publisher(
        notices=object(),  # type: ignore[arg-type]
        uows=uows,  # type: ignore[arg-type]
        achievements=logros,  # type: ignore[arg-type]
    )

    assert publicador._achievements is logros  # type: ignore[attr-defined]


def test_deleting_a_round_tells_activity():
    actividad = object()

    caso = get_delete_round_use_case(uow=object(), actividad=actividad)  # type: ignore[arg-type]

    assert caso._actividad._publisher is actividad


def test_replacing_the_schedule_tells_activity():
    actividad = object()

    caso = get_configure_schedule_use_case(uow=object(), actividad=actividad)  # type: ignore[arg-type]

    assert caso._actividad._publisher is actividad
