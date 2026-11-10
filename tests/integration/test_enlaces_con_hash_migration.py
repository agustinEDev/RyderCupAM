"""
La migración de los enlaces con hash (b7e9d1f3a5c8, fase 3, C3).

Decidido por Agustín: los enlaces pendientes en claro dejan de valer al desplegar. La
migración los borra (sin el token en claro en la BD), deja los que ya son un hash, y
añade la caducidad de la verificación, el aviso de registro y el cupo de restablecer.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text

from tests.integration.test_activity_events_published_at_migration import (
    _alembic,
    base_desechable,  # noqa: F401
)

ANTERIOR = "b3d5f7a9c1e2"
ENLACES = "b7e9d1f3a5c8"
EN_CLARO = "token-en-claro-de-antes-0123456789abcdef0123"
# El SHA-256 de "ya-con-hash", escrito tal cual
HASH = "47249f73f0c502b596946d1a19d679ed2b463da53d7fadcfc632291274fce6a2"


def _usuario(conn, verificacion, reset) -> str:
    user_id = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO users (id, first_name, last_name, email, created_at, updated_at, "
            "email_verified, verification_token, password_reset_token, "
            "reset_token_expires_at) VALUES (:id, 'Ana', 'Garcia', :email, now(), now(), "
            "false, :v, :r, :x)"
        ),
        {
            "id": user_id,
            "email": f"{user_id}@example.com",
            "v": verificacion,
            "r": reset,
            "x": datetime.now() + timedelta(hours=5) if reset else None,
        },
    )
    return user_id


def test_c3_plaintext_links_are_voided_and_hashes_kept(base_desechable):  # noqa: F811
    """
    Given: Cuentas con enlaces en claro, con un hash y sin enlaces, antes de migrar
    When: Se migra
    Then: Los en claro, a NULL (y la caducidad del reset); los hash, igual; columnas
          nuevas con sus valores por defecto
    """
    _alembic(base_desechable, "upgrade", ANTERIOR)
    engine = create_engine(base_desechable)
    with engine.begin() as conn:
        en_claro = _usuario(conn, EN_CLARO, EN_CLARO)
        con_hash = _usuario(conn, HASH, HASH)
        sin_nada = _usuario(conn, None, None)
    engine.dispose()

    _alembic(base_desechable, "upgrade", ENLACES)

    engine = create_engine(base_desechable)
    with engine.connect() as conn:
        filas = {
            f[0]: f[1:]
            for f in conn.execute(
                text(
                    "SELECT id::text, verification_token, password_reset_token, "
                    "reset_token_expires_at IS NOT NULL, verification_token_expires_at, "
                    "register_attempt_notice_at, password_reset_emails_in_window, "
                    "password_reset_window_started_at FROM users"
                )
            ).all()
        }
    engine.dispose()
    assert filas[en_claro] == (None, None, False, None, None, 0, None)
    assert filas[con_hash][:3] == (HASH, HASH, True)
    assert filas[sin_nada] == (None, None, False, None, None, 0, None)


def test_c3_the_migration_goes_down_and_up_again(base_desechable):  # noqa: F811
    """
    Given: La BD migrada
    When: Se baja a la anterior y se vuelve a subir
    Then: Sin error
    """
    _alembic(base_desechable, "upgrade", ENLACES)
    _alembic(base_desechable, "downgrade", ANTERIOR)
    _alembic(base_desechable, "upgrade", ENLACES)
