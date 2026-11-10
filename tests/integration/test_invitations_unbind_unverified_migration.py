"""
La migración que desata las invitaciones de cuentas sin verificar (b3d5f7a9c1e2).

Hasta la 2.56, invitar por correo a una dirección con cuenta SIN verificar ataba
la invitación a esa cuenta (`invitee_user_id`), y por user_id la veía y la
aceptaba sin haber demostrado que el correo era suyo (F-07, fase 3). Ahora:

  M1 PENDIENTE atada a una cuenta sin verificar: se desata (queda «a un correo»)
     y su «Te han invitado» de Actividad desaparece (llevaba el nombre de la privada)
  M2 PENDIENTE atada a una cuenta verificada: no se toca, ni su aviso
  M3 ya respondida (ACCEPTED, DECLINED…) de una cuenta sin verificar: no se toca
  M4 el aviso de otra cosa de esa cuenta: no se toca
  M5 hacia atrás no se vuelve a atar nada (no hay forma de saber cuáles eran)
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text

from tests.integration.test_activity_events_published_at_migration import (
    _alembic,
    base_desechable,  # noqa: F401
)

ANTERIOR = "a2c4e6f8b0d1"
DESATA = "b3d5f7a9c1e2"
AHORA = datetime(2026, 11, 10, 12, 0)


def _usuario(conn, verificado: bool) -> str:
    user_id = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO users (id, first_name, last_name, email, email_verified, "
            "created_at, updated_at) VALUES (:id, 'Ana', 'Garcia', :email, :v, now(), now())"
        ),
        {"id": user_id, "email": f"{user_id}@example.com", "v": verificado},
    )
    return user_id


def _invitacion(conn, competition_id: str, organizador: str, invitado: str, estado: str) -> str:
    invitation_id = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO invitations (id, competition_id, inviter_id, invitee_email, "
            "invitee_user_id, status, expires_at, created_at, updated_at) "
            "VALUES (:id, :c, :o, :e, :u, :s, :x, :n, :n)"
        ),
        {
            "id": invitation_id,
            "c": competition_id,
            "o": organizador,
            "e": f"{invitado}@example.com",
            "u": invitado,
            "s": estado,
            "x": AHORA + timedelta(days=7),
            "n": AHORA,
        },
    )
    return invitation_id


def _aviso(conn, user_id: str, tipo: str, origen: str) -> None:
    conn.execute(
        text(
            "INSERT INTO activity_events (id, user_id, type, occurred_at, published_at, "
            "source_match_id) VALUES (:id, :u, :t, :n, :n, :o)"
        ),
        {"id": str(uuid.uuid4()), "u": user_id, "t": tipo, "n": AHORA, "o": origen},
    )


def _escena(url: str) -> dict:
    engine = create_engine(url)
    with engine.begin() as conn:
        organizador = _usuario(conn, verificado=True)
        sin_verificar = _usuario(conn, verificado=False)
        verificada = _usuario(conn, verificado=True)
        competition_id = str(uuid.uuid4())
        conn.execute(
            text(
                "INSERT INTO competitions (id, creator_id, name, start_date, end_date, "
                "country_code, play_mode, created_at, updated_at) "
                "VALUES (:id, :o, 'Privada', '2026-12-01', '2026-12-02', 'ES', 'SCRATCH', "
                "now(), now())"
            ),
            {"id": competition_id, "o": organizador},
        )
        escena = {
            "sin_verificar": sin_verificar,
            "pendiente_sin_verificar": _invitacion(
                conn, competition_id, organizador, sin_verificar, "PENDING"
            ),
            "aceptada_sin_verificar": _invitacion(
                conn, competition_id, organizador, sin_verificar, "ACCEPTED"
            ),
            "pendiente_verificada": _invitacion(
                conn, competition_id, organizador, verificada, "PENDING"
            ),
        }
        _aviso(conn, sin_verificar, "INVITED_TO_TOURNAMENT", escena["pendiente_sin_verificar"])
        _aviso(conn, sin_verificar, "BIRDIE", "grupo-1")
        # Otro tipo con el mismo origen que la invitación: no es su «Te han invitado»
        _aviso(conn, sin_verificar, "ENROLLED_IN_TOURNAMENT", escena["pendiente_sin_verificar"])
        _aviso(conn, verificada, "INVITED_TO_TOURNAMENT", escena["pendiente_verificada"])
    engine.dispose()
    return escena


def _consulta(url: str, sql: str, **params):
    engine = create_engine(url)
    with engine.connect() as conn:
        filas = conn.execute(text(sql), params).all()
    engine.dispose()
    return filas


def _atada(url: str, invitation_id: str) -> bool:
    ((usuario,),) = _consulta(
        url, "SELECT invitee_user_id FROM invitations WHERE id = :id", id=invitation_id
    )
    return usuario is not None


def _avisos(url: str) -> set[tuple[str, str]]:
    return set(_consulta(url, "SELECT type, source_match_id FROM activity_events"))


def test_m1_a_m4_solo_se_desatan_las_pendientes_de_cuentas_sin_verificar(
    base_desechable,  # noqa: F811
):
    """
    Given: Invitaciones pendientes y respondidas, de cuentas verificadas y sin verificar
    When: Se migra
    Then: Solo la pendiente de la cuenta sin verificar se desata y pierde su aviso
    """
    _alembic(base_desechable, "upgrade", ANTERIOR)
    escena = _escena(base_desechable)

    _alembic(base_desechable, "upgrade", DESATA)

    assert not _atada(base_desechable, escena["pendiente_sin_verificar"])
    assert _atada(base_desechable, escena["aceptada_sin_verificar"])
    assert _atada(base_desechable, escena["pendiente_verificada"])
    assert _avisos(base_desechable) == {
        ("BIRDIE", "grupo-1"),
        ("ENROLLED_IN_TOURNAMENT", escena["pendiente_sin_verificar"]),
        ("INVITED_TO_TOURNAMENT", escena["pendiente_verificada"]),
    }


def test_m5_hacia_atras_no_se_vuelve_a_atar(base_desechable):  # noqa: F811
    """
    Given: La migración aplicada
    When: Se deshace
    Then: Funciona y la invitación sigue «a un correo»
    """
    _alembic(base_desechable, "upgrade", ANTERIOR)
    escena = _escena(base_desechable)
    _alembic(base_desechable, "upgrade", DESATA)

    _alembic(base_desechable, "downgrade", ANTERIOR)

    assert not _atada(base_desechable, escena["pendiente_sin_verificar"])
