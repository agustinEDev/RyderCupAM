"""
Qué correos llevan token (E13b, 7 nov 2026).

Brevo reescribe los enlaces por su servidor: un correo con token (verificar, restablecer
la contraseña, confirmar el correo nuevo) nunca sale por él. Por defecto un correo lleva
token: esta lista fija los únicos que pueden ir por Brevo.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.shared.infrastructure.email.email_service import EmailService
from src.shared.infrastructure.email.envio_de_correo import CorreoSaliente

FUTURO = datetime.now(UTC) + timedelta(days=7)

CORREOS = [
    ("verificacion", True, lambda s: s.send_verification_email("a@b.com", "Ana", "tok")),
    (
        "restablecer",
        True,
        lambda s: s.send_password_reset_email("a@b.com", "https://x/reset/tok", "Ana"),
    ),
    ("confirmar_correo", True, lambda s: s.send_email_change_confirmation("a@b.com", "Ana", "tok")),
    ("cambiada", False, lambda s: s.send_password_changed_notification("a@b.com", "Ana")),
    (
        "cambio_pedido",
        False,
        lambda s: s.send_email_change_requested_notice("a@b.com", "Ana", "nuevo@b.com"),
    ),
    (
        "nuevo_inicio",
        False,
        lambda s: s.send_new_login_notification("a@b.com", "Ana", "iPhone", "hoy", "ES"),
    ),
    (
        "intentos",
        False,
        lambda s: s.send_failed_logins_notification("a@b.com", "Ana", "red", "hoy", "ES", 10, 30),
    ),
    (
        "invitacion",
        False,
        lambda s: s.send_invitation_email("a@b.com", "Ana", "Pablo", "Copa", None, FUTURO),
    ),
    ("amistad", False, lambda s: s.send_friend_request_email("a@b.com", "Ana", "Pablo")),
    (
        "handicaps",
        False,
        lambda s: s.send_handicaps_pending_email("a@b.com", "Ana", "Copa", "c-1", ["Luis"]),
    ),
    (
        "programada",
        False,
        lambda s: s.send_scheduled_handicaps_update_skipped_email(
            "a@b.com", "Ana", "Copa", "c-1", "motivo"
        ),
    ),
]


class _Envio:
    def __init__(self):
        self.correos: list[CorreoSaliente] = []

    async def send(self, correo: CorreoSaliente) -> bool:
        self.correos.append(correo)
        return True


@pytest.mark.parametrize(("nombre", "con_token", "manda"), CORREOS, ids=[c[0] for c in CORREOS])
async def test_e13b_each_email_says_whether_it_carries_a_token(nombre, con_token, manda):
    envio = _Envio()

    await manda(EmailService(envio=envio))

    (correo,) = envio.correos
    assert correo.con_token is con_token, nombre


def test_e13b_every_email_of_the_app_is_in_the_list():
    """Un correo nuevo tiene que entrar en esta tabla: así se decide a propósito si
    lleva token (y si no se marca, cuenta como que sí)."""
    del_servicio = {n for n in dir(EmailService) if n.startswith("send_")}

    assert del_servicio == {
        "send_verification_email",
        "send_password_reset_email",
        "send_email_change_confirmation",
        "send_password_changed_notification",
        "send_email_change_requested_notice",
        "send_new_login_notification",
        "send_failed_logins_notification",
        "send_invitation_email",
        "send_friend_request_email",
        "send_handicaps_pending_email",
        "send_scheduled_handicaps_update_skipped_email",
    }
    assert len(CORREOS) == len(del_servicio)
