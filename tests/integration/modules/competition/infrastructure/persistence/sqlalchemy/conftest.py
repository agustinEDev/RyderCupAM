"""Fixtures compartidos por los tests de persistencia de competición.

`jugadores` y `ronda` nacieron en los tests del repositorio de sobres; los
reutilizan los del motivo de las sesiones sin partidos (BE #361).
"""

from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_envelope_repository import (  # noqa: F401
    jugadores,
    ronda,
)
