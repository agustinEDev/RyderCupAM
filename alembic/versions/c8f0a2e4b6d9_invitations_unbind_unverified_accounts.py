"""invitations: unbind the pending ones of accounts without a verified email

F-07, fase 3 del plan a 9 (10 nov 2026). Hasta ahora, invitar por correo a una
dirección que ya tenía cuenta SIN verificar ataba la invitación a esa cuenta
(`invitee_user_id`), y por user_id la veía, entraba en la privada y la aceptaba
sin haber demostrado que el correo era suyo. Desde esta versión solo se ata a una
cuenta verificada; las pendientes ya atadas a una sin verificar se desatan: quedan
«enviadas a un correo», y la cuenta las verá al verificar su correo, por el casado
por correo. Su «Te han invitado» de Actividad (con el nombre de la competición)
se borra: no se vuelve a publicar.

Solo datos: un UPDATE y un DELETE acotados, compatibles con la versión anterior
durante el despliegue (para ella, una invitación sin user_id es una a un correo).
Hacia atrás no se vuelve a atar nada: no queda forma de saber cuáles eran.

Revision ID: c8f0a2e4b6d9
Revises: a2c4e6f8b0d1
Create Date: 2026-11-10

"""

from alembic import op

revision = "c8f0a2e4b6d9"
down_revision = "a2c4e6f8b0d1"
branch_labels = None
depends_on = None

# Primero los avisos (se reconocen por la invitación aún atada), luego desatar
_BORRA_SUS_AVISOS = """
DELETE FROM activity_events AS ae
USING invitations AS i, users AS u
WHERE ae.type = 'INVITED_TO_TOURNAMENT'
  AND ae.source_match_id = i.id
  AND ae.user_id = i.invitee_user_id
  AND i.invitee_user_id = u.id
  AND i.status = 'PENDING'
  AND u.email_verified = false
"""

_DESATA = """
UPDATE invitations AS i
SET invitee_user_id = NULL
FROM users AS u
WHERE i.invitee_user_id = u.id
  AND i.status = 'PENDING'
  AND u.email_verified = false
"""


def upgrade() -> None:
    op.execute(_BORRA_SUS_AVISOS)
    op.execute(_DESATA)


def downgrade() -> None:
    # No se vuelve a atar: no hay forma de saber cuáles estaban atadas
    pass
