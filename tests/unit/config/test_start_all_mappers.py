"""
Tests de start_all_mappers (#565): la lista única de mappers.

Los arranques se prueban en un proceso limpio, porque la suite ya los ha
arrancado al cargar conftest: dentro de este proceso no se vería ni el primer
arranque ni el segundo.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from src.config import mappers

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_starting_all_mappers_twice_is_harmless():
    """
    GIVEN: Un proceso limpio
    WHEN: Se arrancan todos los mappers dos veces seguidas
    THEN: La segunda no falla (son idempotentes), las tablas son las mismas y
         las entidades quedan mapeadas de verdad (las tablas solas se
         registran al importar, aunque no se mapee nada)
    """
    result = _run(
        "from sqlalchemy import inspect\n"
        "from src.config.mappers import start_all_mappers\n"
        "from src.modules.competition.domain.entities.competition import Competition\n"
        "from src.modules.golf_course.domain.entities.golf_course import GolfCourse\n"
        "from src.shared.infrastructure.persistence.sqlalchemy.base import metadata\n"
        "start_all_mappers()\n"
        "first = sorted(metadata.tables)\n"
        "start_all_mappers()\n"
        "print('SAME=' + str(first == sorted(metadata.tables) and len(first) > 0))\n"
        "mapped = all(inspect(c, raiseerr=False) is not None for c in (GolfCourse, Competition))\n"
        "print('MAPPED=' + str(mapped))\n"
    )

    assert result.returncode == 0, result.stderr[-2000:]
    lines = result.stdout.splitlines()
    assert "SAME=True" in lines
    assert "MAPPED=True" in lines


def test_golf_course_is_mapped_before_competition():
    """
    GIVEN: La lista única de mappers
    WHEN: Se arranca
    THEN: GolfCourse va antes que Competition, que la referencia en una relación
         (al revés: `UnmappedClassError: Class GolfCourse is not mapped`)
    """
    order = []
    names = [
        "start_user_mappers",
        "start_country_mappers",
        "start_golf_course_mappers",
        "start_competition_mappers",
        "start_social_mappers",
        "start_profile_photo_mappers",
        "start_activity_event_mappers",
        "start_quick_match_mappers",
    ]
    patches = [
        patch.object(mappers, name, side_effect=lambda name=name: order.append(name))
        for name in names
    ]
    for p in patches:
        p.start()
    try:
        mappers.start_all_mappers()
    finally:
        for p in patches:
            p.stop()

    assert sorted(order) == sorted(names)
    assert order.index("start_golf_course_mappers") < order.index("start_competition_mappers")
