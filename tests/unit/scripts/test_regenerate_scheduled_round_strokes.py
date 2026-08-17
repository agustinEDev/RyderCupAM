"""
Tests del arranque del comando que regenera los golpes de las rondas SCHEDULED.

Solo cubren el registro del mapeo imperativo: lo que el comando hace con la base
de datos se prueba a través del caso de uso que invoca.

El resto de la suite no vale para esto. `conftest.py` ya deja los mappers
registrados antes de cualquier test, así que un test que se limite a ejecutar el
comando pasa aunque el comando no los registre — que es justo como el fallo
llegó hasta una ejecución real contra una base de datos.
"""

import asyncio
from unittest.mock import patch

import pytest

from scripts import regenerate_scheduled_round_strokes as command


def test_the_command_registers_the_mappers_before_querying():
    """
    GIVEN: El comando ejecutado fuera de la aplicación
    WHEN: Arranca
    THEN: Registra el mapeo imperativo antes de abrir la sesión

    Sin esto la primera consulta muere con `ArgumentError: Column expression,
    FROM clause, or other columns clause element expected, got <class
    Competition>`: fuera de `main.py` y de `alembic/env.py` nadie registra el
    mapeo de las entidades de dominio.
    """
    order = []

    with (
        patch.object(command, "start_mappers", side_effect=lambda: order.append("mappers")),
        patch.object(
            command,
            "async_session_maker",
            side_effect=lambda: order.append("session") or _RaisingSession(),
        ),
        pytest.raises(_SessionOpenedError),
    ):
        asyncio.run(command.main(dry_run=True))

    assert order == ["mappers", "session"]


def test_the_mappers_are_registered_with_golf_course_before_competition():
    """
    GIVEN: El registro del mapeo del comando
    WHEN: Se ejecuta
    THEN: GolfCourse se registra antes que Competition

    Competition referencia a GolfCourse en una relación, y al revés SQLAlchemy
    falla con `UnmappedClassError: Class GolfCourse is not mapped`.
    """
    order = []

    with (
        patch.object(command, "start_user_mappers", side_effect=lambda: order.append("user")),
        patch.object(command, "start_country_mappers", side_effect=lambda: order.append("country")),
        patch.object(
            command, "start_golf_course_mappers", side_effect=lambda: order.append("golf_course")
        ),
        patch.object(
            command, "start_competition_mappers", side_effect=lambda: order.append("competition")
        ),
    ):
        command.start_mappers()

    assert order.index("golf_course") < order.index("competition")


class _SessionOpenedError(Exception):
    """Corta la ejecución en cuanto el comando pide una sesión."""


class _RaisingSession:
    """Sesión de mentira: solo sirve para saber que se ha llegado a pedirla."""

    async def __aenter__(self):
        raise _SessionOpenedError

    async def __aexit__(self, *_):
        return False
