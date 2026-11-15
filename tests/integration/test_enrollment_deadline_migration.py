"""
La migración del plazo de inscripción (15 nov 2026) sobre competiciones de antes.

    caso | antes de migrar                          | después
    -----|------------------------------------------|----------------------------------------
    A1   | apertura programada a 1 día              | a 2 días; las de 5 y sin programar, igual
    R1   | ACTIVE de antes                          | abierta «ahora»: el cierre automático no
         |                                          | cierra de golpe lo que ya pasó su plazo
    R1   | DRAFT o CLOSED de antes                  | sin fecha de apertura
    C3   | cualquiera                               | sin cerrar por el plazo y sin aviso dado
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine, text

from tests.integration.test_activity_events_published_at_migration import (
    _alembic,
    base_desechable,  # noqa: F401
)

ANTERIOR = "f9b1d3e5a7c9"
PLAZO = "c8e1a3f5b7d9"


def _competicion(conn, creador: str, estado: str, dias: int | None) -> str:
    competicion = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO competitions (id, creator_id, name, start_date, end_date, country_code, "
            "play_mode, max_players, status, enrollment_opens_days_before, created_at, "
            "updated_at) VALUES (:id, :u, :n, :s, :e, 'ES', 'SCRATCH', 12, :st, :d, now(), now())"
        ),
        {
            "id": competicion,
            "u": creador,
            "n": f"Plazo {competicion[:8]}",
            "s": date(2026, 1, 10),
            "e": date(2026, 1, 11),
            "st": estado,
            "d": dias,
        },
    )
    return competicion


def test_the_old_competitions_get_their_deadline_columns(base_desechable):  # noqa: F811
    """
    A1, R1, C3. Given competiciones de antes de la migración, una con apertura a 1 día
    When se migra
    Then 1 pasa a 2, la ACTIVE queda abierta ahora y ninguna cerrada por el plazo
    """
    _alembic(base_desechable, "upgrade", ANTERIOR)
    engine = create_engine(base_desechable)
    with engine.begin() as conn:
        creador = str(uuid.uuid4())
        conn.execute(
            text(
                "INSERT INTO users (id, first_name, last_name, email, created_at, updated_at) "
                "VALUES (:id, 'Ana', 'Garcia', :email, now(), now())"
            ),
            {"id": creador, "email": f"{creador}@example.com"},
        )
        a_un_dia = _competicion(conn, creador, "DRAFT", 1)
        a_cinco = _competicion(conn, creador, "DRAFT", 5)
        abierta = _competicion(conn, creador, "ACTIVE", None)
        cerrada = _competicion(conn, creador, "CLOSED", None)
    engine.dispose()

    _alembic(base_desechable, "upgrade", PLAZO)

    engine = create_engine(base_desechable)
    with engine.connect() as conn:
        filas = {
            fila.id: fila
            for fila in conn.execute(
                text(
                    "SELECT id::text AS id, enrollment_opens_days_before AS dias, "
                    "enrollment_opened_at AS abierta, enrollment_closed_by_deadline AS por_plazo, "
                    "enrollment_close_blocked_notified AS avisada FROM competitions"
                )
            )
        }
    engine.dispose()

    assert filas[a_un_dia].dias == 2
    assert filas[a_cinco].dias == 5
    assert filas[abierta].dias is None
    assert filas[abierta].abierta is not None
    # En UTC, y de ahora (con margen: el reloj de la base no es el de los tests)
    ahora = datetime.now(UTC).replace(tzinfo=None)
    assert abs(filas[abierta].abierta - ahora) < timedelta(minutes=5)
    assert filas[a_un_dia].abierta is None
    assert filas[cerrada].abierta is None
    assert all(not f.por_plazo and not f.avisada for f in filas.values())


def test_it_goes_back(base_desechable):  # noqa: F811
    """Given migrada / When se baja una / Then las columnas nuevas se van."""
    _alembic(base_desechable, "upgrade", PLAZO)
    _alembic(base_desechable, "downgrade", ANTERIOR)

    engine = create_engine(base_desechable)
    with engine.connect() as conn:
        columnas = {
            fila[0]
            for fila in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'competitions'"
                )
            )
        }
    engine.dispose()
    assert not columnas & {
        "enrollment_opened_at",
        "enrollment_closed_by_deadline",
        "enrollment_close_blocked_notified",
    }
