"""
El aviso al dueño cuando alguien se registra con su correo (fase 3, B2).

Bilingüe como los demás avisos de seguridad (la cuenta no guarda idioma), con texto y
HTML, el botón de iniciar sesión y el de restablecer, y sin token: no lleva nada que
dé acceso a la cuenta.
"""

from src.config.settings import settings
from src.shared.infrastructure.email.email_service import EmailService
from src.shared.infrastructure.email.envio_de_correo import CorreoSaliente


class _Envio:
    def __init__(self):
        self.correos: list[CorreoSaliente] = []

    async def send(self, correo: CorreoSaliente) -> bool:
        self.correos.append(correo)
        return True


async def _aviso() -> CorreoSaliente:
    envio = _Envio()
    assert await EmailService(envio=envio).send_register_attempt_notice("ana@b.com", "Ana")
    (correo,) = envio.correos
    return correo


async def test_b2_the_notice_goes_to_the_owner_in_both_languages():
    """
    Given: El aviso de intento de registro
    When: Se envía
    Then: Al dueño, con asunto, texto y HTML en español y en inglés
    """
    correo = await _aviso()

    assert "ana@b.com" in correo.to
    assert "registrarse" in correo.subject and "sign up" in correo.subject
    for parte in (correo.text, correo.html):
        assert "Alguien ha intentado registrarse con tu correo" in parte
        assert "Someone tried to sign up with your email" in parte


async def test_b2_the_notice_links_to_sign_in_and_reset_and_carries_no_token():
    """
    Given: El aviso de intento de registro
    When: Se envía
    Then: Enlaza a iniciar sesión y a «Olvidé mi contraseña»; nada más de la cuenta
    """
    correo = await _aviso()

    for parte in (correo.text, correo.html):
        assert f"{settings.FRONTEND_URL}/login" in parte
        assert f"{settings.FRONTEND_URL}/forgot-password" in parte
    assert "token" not in correo.text.lower() and "token=" not in correo.html
    assert correo.puede_ir_por_brevo is False
