"""
El adaptador que manda el mensaje de contacto (C1, C5), ya sobre la pieza común de
envío (E7, 7 nov 2026): Mailgun con Brevo de respaldo, o Mailpit en el Kind.
"""

from src.modules.support.infrastructure.services.mailgun_contact_mailer import ContactMailer
from src.shared.infrastructure.email.envio_de_correo import CorreoSaliente


class _Envio:
    def __init__(self, sale=True):
        self.sale = sale
        self.correos: list[CorreoSaliente] = []

    async def send(self, correo: CorreoSaliente) -> bool:
        self.correos.append(correo)
        return self.sale


def _mailer(envio):
    return ContactMailer(envio=envio, to_email="admin@rydercupfriends.com")


async def test_it_goes_to_admin_with_reply_to_and_text_only():
    """
    Given: Un mensaje con un remitente ASCII
    When: Se manda
    Then: True; a admin@, con «Responder a» quien escribe y sin HTML
    """
    envio = _Envio()

    enviado = await _mailer(envio).send(
        subject="[Contacto · Pregunta] Hola", text="Cuerpo", reply_to="ana@example.com"
    )

    assert enviado is True
    assert envio.correos == [
        CorreoSaliente(
            to="admin@rydercupfriends.com",
            subject="[Contacto · Pregunta] Hola",
            text="Cuerpo",
            reply_to="ana@example.com",
            # Ni token ni seguridad: puede salir por Brevo si Mailgun y Resend no pueden
            puede_ir_por_brevo=True,
        )
    ]


async def test_a_non_ascii_reply_to_is_left_out():
    """Una dirección con tildes no cabe en una cabecera: sin «Responder a» (va en el cuerpo)."""
    envio = _Envio()

    await _mailer(envio).send(subject="S", text="T", reply_to="josé@ejemplo.es")

    assert envio.correos[0].reply_to is None


async def test_it_says_false_when_it_did_not_go_out():
    """Si el envío no sale (cupo, red, sin clave), False: la ruta responde 502."""
    assert (
        await _mailer(_Envio(sale=False)).send(subject="S", text="T", reply_to="a@b.com") is False
    )


async def test_by_default_it_goes_to_the_configured_mailbox(monkeypatch):
    """Sin destinatario, el buzón de CONTACT_EMAIL."""
    from src.config.settings import settings

    monkeypatch.setattr(settings, "CONTACT_EMAIL", "otro@example.com")
    envio = _Envio()

    await ContactMailer(envio=envio).send(subject="S", text="T", reply_to="a@b.com")

    assert envio.correos[0].to == "otro@example.com"
