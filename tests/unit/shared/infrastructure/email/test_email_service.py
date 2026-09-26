"""
Tests de los correos que manda la aplicación (BE #389).

Los cinco comparten una plantilla con la imagen de la app. Se comprueba lo
que llega a Mailgun —asunto, texto plano y HTML— sustituyendo el envío, sin
red: el enlace de cada botón, que nada del usuario entra sin escapar y que el
HTML no depende de un <style> que Gmail borra.
"""

import re
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.config.settings import settings
from src.shared.infrastructure.email.email_service import EmailService

WEB = "https://www.rydercupfriends.com"


@pytest.fixture
def correo(monkeypatch):
    """El servicio con el envío sustituido: guarda lo que se mandaría."""
    monkeypatch.setattr(settings, "FRONTEND_URL", WEB)
    servicio = EmailService()
    servicio._send_email = MagicMock(return_value=True)
    return servicio


def _enviado(servicio):
    """(destinatario, asunto, texto, html) del único envío."""
    servicio._send_email.assert_called_once()
    args, kwargs = servicio._send_email.call_args
    valores = list(args) + [kwargs[k] for k in ("to", "subject", "text", "html") if k in kwargs]
    return tuple(valores)


def _botones(html_body):
    """Los enlaces de los botones, en orden."""
    return re.findall(r'<a [^>]*data-boton[^>]*href="([^"]+)"', html_body)


async def _los_cinco(servicio):
    """Manda los cinco correos y devuelve el HTML de cada uno."""
    htmls = {}

    servicio.send_verification_email("a@b.com", "Ana", "tok123")
    htmls["verificacion"] = _enviado(servicio)[3]
    servicio._send_email.reset_mock()

    await servicio.send_password_reset_email("a@b.com", f"{WEB}/reset-password/tok", "Ana")
    htmls["restablecer"] = _enviado(servicio)[3]
    servicio._send_email.reset_mock()

    await servicio.send_password_changed_notification("a@b.com", "Ana")
    htmls["cambiada"] = _enviado(servicio)[3]
    servicio._send_email.reset_mock()

    await servicio.send_invitation_email(
        "a@b.com", "Ana", "Pablo", "Copa", None, datetime.now(UTC) + timedelta(days=7)
    )
    htmls["invitacion"] = _enviado(servicio)[3]
    servicio._send_email.reset_mock()

    await servicio.send_friend_request_email("a@b.com", "Ana", "Pablo")
    htmls["amistad"] = _enviado(servicio)[3]
    return htmls


class TestEveryEmailWearsTheAppsBranding:
    """Una sola plantilla con la cara de la app para los cinco."""

    @pytest.mark.asyncio
    async def test_all_five_carry_the_logo_and_the_app_green(self, correo):
        for nombre, cuerpo in (await _los_cinco(correo)).items():
            # El monograma blanco, sobre la cabecera verde de la app
            cabecera = re.search(
                r'<td style="background:(#[0-9a-f]{6});[^"]*">\s*<table[^>]*><tr>\s*'
                r'<td[^>]*><img src="([^"]+)"',
                cuerpo,
            )
            assert cabecera, nombre
            assert cabecera.group(1) == "#15803d", nombre
            assert cabecera.group(2) == f"{WEB}/images/rcf-monogram-white.png", nombre

    @pytest.mark.asyncio
    async def test_no_email_depends_on_a_style_block(self, correo):
        # Gmail borra los <style>: todo va en línea
        for nombre, cuerpo in (await _los_cinco(correo)).items():
            assert "<style" not in cuerpo, nombre

    @pytest.mark.asyncio
    async def test_the_footer_says_the_current_year(self, correo):
        anio = str(datetime.now(UTC).year)
        for nombre, cuerpo in (await _los_cinco(correo)).items():
            assert f"© {anio} RyderCupFriends" in cuerpo, nombre
            assert "2025" not in cuerpo or anio == "2025", nombre

    @pytest.mark.asyncio
    async def test_every_email_has_an_english_block_with_its_own_button(self, correo):
        for nombre, cuerpo in (await _los_cinco(correo)).items():
            assert "English" in cuerpo, nombre
            assert len(_botones(cuerpo)) >= 2, nombre


class TestTheButtonsGoWhereTheySay:
    """Cada botón lleva a una pantalla que existe."""

    def test_verification_goes_to_verify_email_with_its_token(self, correo):
        correo.send_verification_email("a@b.com", "Ana", "tok123")
        _, _, texto, cuerpo = _enviado(correo)
        assert _botones(cuerpo)[0] == f"{WEB}/verify-email?token=tok123"
        assert f"{WEB}/verify-email?token=tok123" in texto

    @pytest.mark.asyncio
    async def test_reset_puts_the_link_in_the_button_and_the_fallback(self, correo):
        enlace = f"{WEB}/reset-password/abc"
        await correo.send_password_reset_email("a@b.com", enlace, "Ana")
        _, _, texto, cuerpo = _enviado(correo)
        assert _botones(cuerpo)[0] == enlace
        # El enlace a mano, por si el botón no funciona
        assert cuerpo.count(enlace) >= 3
        assert "24 horas" in cuerpo and "24 hours" in cuerpo
        assert enlace in texto

    @pytest.mark.asyncio
    async def test_password_changed_offers_to_reset_it(self, correo):
        await correo.send_password_changed_notification("a@b.com", "Ana")
        _, _, _, cuerpo = _enviado(correo)
        assert _botones(cuerpo)[0] == f"{WEB}/forgot-password"

    @pytest.mark.asyncio
    async def test_the_invitation_opens_the_players_invitations(self, correo):
        # Llevaba a /invitations, que no existe: el invitado veía una página en blanco
        await correo.send_invitation_email(
            "a@b.com", "Ana", "Pablo", "Copa", None, datetime(2026, 10, 3, tzinfo=UTC)
        )
        _, _, texto, cuerpo = _enviado(correo)
        assert _botones(cuerpo)[0] == f"{WEB}/player/invitations"
        assert f"{WEB}/player/invitations" in texto
        assert f'"{WEB}/invitations"' not in cuerpo

    @pytest.mark.asyncio
    async def test_an_invitee_without_account_also_gets_the_register_button(self, correo):
        await correo.send_invitation_email(
            "a@b.com", None, "Pablo", "Copa", None, datetime(2026, 10, 3, tzinfo=UTC)
        )
        _, _, _, cuerpo = _enviado(correo)
        assert f"{WEB}/register" in _botones(cuerpo)

    @pytest.mark.asyncio
    async def test_a_registered_invitee_gets_no_register_button(self, correo):
        await correo.send_invitation_email(
            "a@b.com", "Ana", "Pablo", "Copa", None, datetime(2026, 10, 3, tzinfo=UTC)
        )
        _, _, _, cuerpo = _enviado(correo)
        assert f"{WEB}/register" not in _botones(cuerpo)

    @pytest.mark.asyncio
    async def test_the_friend_request_opens_the_friends_screen(self, correo):
        await correo.send_friend_request_email("a@b.com", "Ana", "Pablo")
        _, _, _, cuerpo = _enviado(correo)
        assert _botones(cuerpo)[0] == f"{WEB}/friends"


class TestNothingFromTheUserEntersUnescaped:
    """Nombres y mensajes los escribe la gente: nunca entran como HTML."""

    def test_a_name_with_an_ampersand_is_escaped_in_the_verification(self, correo):
        correo.send_verification_email("a@b.com", "Tom & Jerry's", "t")
        _, _, _, cuerpo = _enviado(correo)
        assert "Tom &amp; Jerry&#x27;s" in cuerpo
        assert "Tom & Jerry's" not in cuerpo

    @pytest.mark.asyncio
    async def test_a_name_with_an_ampersand_is_escaped_when_the_password_changes(self, correo):
        await correo.send_password_changed_notification("a@b.com", "Tom & Jerry")
        _, _, _, cuerpo = _enviado(correo)
        assert "Tom &amp; Jerry" in cuerpo

    @pytest.mark.asyncio
    async def test_the_personal_message_cannot_inject_markup(self, correo):
        await correo.send_invitation_email(
            "a@b.com",
            "Ana",
            "Pablo",
            "Copa & Cena",
            '<script>alert("x")</script>',
            datetime(2026, 10, 3, tzinfo=UTC),
        )
        _, _, _, cuerpo = _enviado(correo)
        assert "<script>" not in cuerpo
        assert "&lt;script&gt;" in cuerpo
        assert "Copa &amp; Cena" in cuerpo


class TestTheInvitationContent:
    """Lo que dice la invitación."""

    @pytest.mark.asyncio
    async def test_the_quote_appears_only_with_a_personal_message(self, correo):
        caduca = datetime(2026, 10, 3, tzinfo=UTC)
        await correo.send_invitation_email("a@b.com", "Ana", "Pablo", "Copa", None, caduca)
        sin_mensaje = _enviado(correo)[3]
        correo._send_email.reset_mock()
        await correo.send_invitation_email(
            "a@b.com", "Ana", "Pablo", "Copa", "Te esperamos", caduca
        )
        con_mensaje = _enviado(correo)[3]

        assert "data-cita" not in sin_mensaje
        assert "data-cita" in con_mensaje
        assert "Te esperamos" in con_mensaje

    @pytest.mark.asyncio
    async def test_it_says_who_invites_to_what_and_until_when(self, correo):
        await correo.send_invitation_email(
            "a@b.com", "Ana", "Pablo Noche", "Copa", None, datetime(2026, 10, 3, tzinfo=UTC)
        )
        _, asunto, texto, cuerpo = _enviado(correo)
        assert "Pablo Noche te invita a jugar" in cuerpo
        assert "Copa" in cuerpo
        assert "03/10/2026" in cuerpo
        assert "Copa" in asunto
        assert "03/10/2026" in texto
