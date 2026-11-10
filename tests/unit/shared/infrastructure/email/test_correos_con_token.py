"""
Qué correos pueden salir por Brevo (E13b, 7 nov 2026).

Brevo reescribe los enlaces por su servidor: nunca un correo con token (verificar,
restablecer la contraseña, confirmar el correo nuevo) ni un aviso de seguridad (nuevo
inicio de sesión, intentos fallidos, contraseña cambiada, cambio de correo pedido):
un enlace de seguridad por un dominio ajeno enseña a fiarse de enlaces raros (Agustín,
tras las revisiones). Por defecto, no: esta lista fija los únicos que pueden.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.shared.infrastructure.email.email_service import EmailService
from src.shared.infrastructure.email.envio_de_correo import CorreoSaliente

FUTURO = datetime.now(UTC) + timedelta(days=7)

CORREOS = [
    ("verificacion", False, lambda s: s.send_verification_email("a@b.com", "Ana", "tok")),
    (
        "restablecer",
        False,
        lambda s: s.send_password_reset_email("a@b.com", "https://x/reset/tok", "Ana"),
    ),
    (
        "confirmar_correo",
        False,
        lambda s: s.send_email_change_confirmation("a@b.com", "Ana", "tok"),
    ),
    ("cambiada", False, lambda s: s.send_password_changed_notification("a@b.com", "Ana")),
    (
        "cambio_pedido",
        False,
        lambda s: s.send_email_change_requested_notice("a@b.com", "Ana", "nuevo@b.com"),
    ),
    (
        "correo_cambiado",
        False,
        lambda s: s.send_email_changed_notice("a@b.com", "Ana", "nuevo@b.com"),
    ),
    (
        "cuenta_asegurada",
        False,
        lambda s: s.send_account_secured_notice("a@b.com", "Ana", "google"),
    ),
    (
        "intento_de_registro",
        False,
        lambda s: s.send_register_attempt_notice("a@b.com", "Ana"),
    ),
    (
        "google",
        False,
        lambda s: s.send_google_account_notice("a@b.com", "Ana", True),
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
        True,
        lambda s: s.send_invitation_email("a@b.com", "Ana", "Pablo", "Copa", None, FUTURO),
    ),
    ("amistad", True, lambda s: s.send_friend_request_email("a@b.com", "Ana", "Pablo")),
    (
        "handicaps",
        True,
        lambda s: s.send_handicaps_pending_email("a@b.com", "Ana", "Copa", "c-1", ["Luis"]),
    ),
    (
        "programada",
        True,
        lambda s: s.send_scheduled_handicaps_update_skipped_email(
            "a@b.com", "Ana", "Copa", "c-1", "motivo"
        ),
    ),
]


def test_r6_a_backslash_in_a_name_is_removed():
    """Una barra invertida en el nombre rompía el destinatario '"nombre" <correo>'."""
    assert "\\" not in EmailService(envio=_Envio())._sanitize_name("evil@x.com\\")


class _Envio:
    def __init__(self):
        self.correos: list[CorreoSaliente] = []

    async def send(self, correo: CorreoSaliente) -> bool:
        self.correos.append(correo)
        return True


@pytest.mark.parametrize(("nombre", "por_brevo", "manda"), CORREOS, ids=[c[0] for c in CORREOS])
async def test_e13b_each_email_says_whether_it_may_go_through_brevo(nombre, por_brevo, manda):
    envio = _Envio()

    await manda(EmailService(envio=envio))

    (correo,) = envio.correos
    assert correo.puede_ir_por_brevo is por_brevo, nombre


def test_e13b_every_email_of_the_app_is_in_the_list():
    """Un correo nuevo tiene que entrar en esta tabla: así se decide a propósito si puede
    ir por Brevo (y si no se marca, no puede)."""
    del_servicio = {n for n in dir(EmailService) if n.startswith("send_")}

    assert del_servicio == {
        "send_verification_email",
        "send_password_reset_email",
        "send_email_change_confirmation",
        "send_password_changed_notification",
        "send_email_change_requested_notice",
        "send_email_changed_notice",
        "send_account_secured_notice",
        "send_google_account_notice",
        "send_register_attempt_notice",
        "send_new_login_notification",
        "send_failed_logins_notification",
        "send_invitation_email",
        "send_friend_request_email",
        "send_handicaps_pending_email",
        "send_scheduled_handicaps_update_skipped_email",
    }
    assert len(CORREOS) == len(del_servicio)
