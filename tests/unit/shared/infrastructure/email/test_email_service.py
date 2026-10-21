"""
Tests de los correos que manda la aplicación (BE #389).

Los cinco comparten una plantilla con la imagen de la app. Se comprueba lo
que llega a Mailgun —asunto, texto plano y HTML— sustituyendo el envío, sin
red: el enlace de cada botón, que nada del usuario entra sin escapar y que el
HTML no depende de un <style> que Gmail borra.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
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

    # Sin cuenta y con mensaje: el botón secundario de registrarse y la cita
    await servicio.send_invitation_email(
        "a@b.com", None, "Pablo", "Copa", "¡Vente!", datetime.now(UTC) + timedelta(days=7)
    )
    htmls["invitacion_sin_cuenta"] = _enviado(servicio)[3]
    servicio._send_email.reset_mock()

    await servicio.send_friend_request_email("a@b.com", "Ana", "Pablo")
    htmls["amistad"] = _enviado(servicio)[3]
    servicio._send_email.reset_mock()

    # El sexto, desde el 7 oct 2026 (#251): el nombre de la función se quedó
    await servicio.send_handicaps_pending_email("a@b.com", "Ana", "Copa", "c-1", ["Luis"])
    htmls["handicaps"] = _enviado(servicio)[3]
    servicio._send_email.reset_mock()

    await servicio.send_scheduled_handicaps_update_skipped_email(
        "a@b.com", "Ana", "Copa", "c-1", "Hay una jornada en marcha."
    )
    htmls["programada"] = _enviado(servicio)[3]
    return htmls


class TestEveryEmailWearsTheAppsBranding:
    """Una sola plantilla con la cara de la app para los cinco."""

    @pytest.mark.asyncio
    async def test_all_five_carry_the_logo_and_the_app_green(self, correo):
        for nombre, cuerpo in (await _los_cinco(correo)).items():
            # El monograma blanco, sobre la cabecera verde de la app
            cabecera = re.search(
                r'<td bgcolor="#[0-9a-f]{6}" style="background:(#[0-9a-f]{6});[^"]*">\s*'
                r"<table[^>]*><tr>\s*"
                r'<td[^>]*><img src="([^"]+)"',
                cuerpo,
            )
            assert cabecera, nombre
            assert cabecera.group(1) == "#15803d", nombre
            assert cabecera.group(2) == f"{WEB}/images/rcf-monogram-white.png", nombre

    @pytest.mark.asyncio
    async def test_no_email_depends_on_a_style_block(self, correo):
        # Gmail borra los <style>: todo va en línea. El único es el del modo
        # claro para Apple Mail, que sin él solo pierde ese refuerzo
        for nombre, cuerpo in (await _los_cinco(correo)).items():
            assert cuerpo.count("<style") == 1, nombre
            assert "<style>:root{color-scheme:light only;" in cuerpo, nombre

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


class TestEveryEmailRepeatsItsLink:
    """El enlace a mano bajo el botón, por si no se puede pulsar (CodeRabbit en
    la PR #390: la #389 lo pide en los cinco, y solo lo llevaban dos)."""

    @pytest.mark.asyncio
    async def test_all_five_repeat_the_main_link_below_the_button(self, correo):
        for nombre, cuerpo in (await _los_cinco(correo)).items():
            principal = _botones(cuerpo)[0]
            assert "¿No funciona el botón?" in cuerpo, nombre
            assert f">{principal}</a>" in cuerpo, nombre


@dataclass
class _Nodo:
    etiqueta: str
    attrs: dict[str, str]
    padre: "_Nodo | None" = None
    hijos: list["_Nodo"] = field(default_factory=list)
    texto: str = ""

    @property
    def estilo(self) -> str:
        return self.attrs.get("style") or ""

    def todos(self):
        yield self
        for hijo in self.hijos:
            yield from hijo.todos()

    def ancestros(self):
        nodo = self.padre
        while nodo is not None:
            yield nodo
            nodo = nodo.padre


_VACIAS = {"meta", "img", "br", "hr", "link", "input"}


class _Arbol(HTMLParser):
    """Un árbol mínimo del HTML, sin cerrar nada por su cuenta: un <p> dentro
    de otro <p> se queda dentro, y así se ve."""

    def __init__(self, html_body):
        super().__init__(convert_charrefs=True)
        self.raiz = _Nodo("#raiz", {})
        self._actual = self.raiz
        self.feed(html_body)

    def handle_starttag(self, tag, attrs):
        nodo = _Nodo(tag, {k: v or "" for k, v in attrs}, padre=self._actual)
        self._actual.hijos.append(nodo)
        if tag not in _VACIAS:
            self._actual = nodo

    def handle_endtag(self, tag):
        nodo = self._actual
        while nodo is not None and nodo.etiqueta != tag:
            nodo = nodo.padre
        assert nodo is not None, f"</{tag}> sin abrir"
        self._actual = nodo.padre

    def handle_data(self, data):
        self._actual.texto += data


def _arbol(html_body):
    return _Arbol(html_body).raiz


def _nodos(html_body, etiqueta):
    return [n for n in _arbol(html_body).todos() if n.etiqueta == etiqueta]


def _anclas_de_boton(html_body):
    return [n for n in _nodos(html_body, "a") if "data-boton" in n.attrs]


def _fondo(nodo):
    encontrado = re.search(r"(?:^|;)background:(#[0-9a-fA-F]{3,6})", nodo.estilo)
    return encontrado.group(1) if encontrado else None


VERDE = "#15803d"
BLANCO = "#ffffff"


class TestTheLayoutStaysLightInAppleMailDarkMode:
    """En Mail de iOS con modo oscuro el aviso del 21 oct perdió la cabecera
    verde y el botón: el fondo puesto solo por CSS desaparecía. Se pide modo
    claro, el color va también en `bgcolor` y los botones son de tabla."""

    @pytest.mark.asyncio
    async def test_the_head_asks_for_light_mode_only(self, correo):
        for nombre, cuerpo in (await _los_cinco(correo)).items():
            cabeza = cuerpo.split("</head>")[0]
            assert '<meta name="color-scheme" content="light only">' in cabeza, nombre
            assert '<meta name="supported-color-schemes" content="light only">' in cabeza, nombre
            assert (
                "<style>:root{color-scheme:light only;supported-color-schemes:light only;}</style>"
                in cabeza
            ), nombre

    @pytest.mark.asyncio
    async def test_every_coloured_background_also_carries_bgcolor(self, correo):
        for nombre, cuerpo in (await _los_cinco(correo)).items():
            con_fondo = [n for n in _arbol(cuerpo).todos() if _fondo(n)]
            for nodo in con_fondo:
                assert nodo.attrs.get("bgcolor") == _fondo(nodo), (
                    nombre,
                    nodo.etiqueta,
                    nodo.estilo,
                )
            colores = {_fondo(n) for n in con_fondo}
            # Página, tarjeta, cabecera y pie, como mínimo
            assert {"#eef2ee", BLANCO, VERDE, "#f8faf8"} <= colores, (nombre, colores)
            cuerpo_html = _nodos(cuerpo, "body")[0]
            assert cuerpo_html.attrs.get("bgcolor") == "#eef2ee", nombre

    @pytest.mark.asyncio
    async def test_the_boxes_carry_bgcolor_too(self, correo):
        htmls = await _los_cinco(correo)
        cajas = {
            "recuadro": (htmls["invitacion"], "#f0faf3"),
            "cita": (htmls["invitacion_sin_cuenta"], "#f6f7f6"),
            "aviso": (htmls["cambiada"], "#fff7ed"),
        }
        for caja, (cuerpo, color) in cajas.items():
            celdas = [n for n in _nodos(cuerpo, "td") if _fondo(n) == color]
            assert celdas, caja
            assert all(c.attrs.get("bgcolor") == color for c in celdas), caja

    @pytest.mark.asyncio
    async def test_primary_buttons_are_bulletproof(self, correo):
        for nombre, cuerpo in (await _los_cinco(correo)).items():
            ancla = _anclas_de_boton(cuerpo)[0]
            self._es_a_prueba_de_balas(ancla, fondo=VERDE, letra=BLANCO, nombre=nombre)
            assert "border:" not in ancla.padre.estilo, nombre

    @pytest.mark.asyncio
    async def test_secondary_buttons_are_bulletproof_with_a_green_border(self, correo):
        htmls = await _los_cinco(correo)
        for nombre, cuerpo in htmls.items():
            secundarios = _anclas_de_boton(cuerpo)[1:]
            assert secundarios, nombre
            for ancla in secundarios:
                self._es_a_prueba_de_balas(ancla, fondo=BLANCO, letra=VERDE, nombre=nombre)
                assert f"border:2px solid {VERDE};" in ancla.padre.estilo, nombre
        # Registrarse + el inglés
        assert len(_anclas_de_boton(htmls["invitacion_sin_cuenta"])) == 3

    @staticmethod
    def _es_a_prueba_de_balas(ancla, *, fondo, letra, nombre):
        celda = ancla.padre
        # El color lo pone la celda, por atributo y por estilo
        assert celda.etiqueta == "td", nombre
        assert celda.attrs.get("bgcolor") == fondo, nombre
        assert _fondo(celda) == fondo, nombre
        assert "border-radius:10px" in celda.estilo, nombre
        # El enlace solo es texto: ni fondo ni bloque propio
        assert "background" not in ancla.estilo, nombre
        assert "display:block" not in ancla.estilo, nombre
        assert "display:inline-block;width:100%;" in ancla.estilo, nombre
        assert f"color:{letra};" in ancla.estilo, nombre
        assert "padding:" in ancla.estilo, nombre
        # Y el color, otra vez en un span alrededor del texto
        assert len(ancla.hijos) == 1, nombre
        span = ancla.hijos[0]
        assert span.etiqueta == "span", nombre
        assert span.estilo == f"color:{letra};", nombre
        assert span.texto.strip(), nombre
        assert not ancla.texto.strip(), nombre

    @pytest.mark.asyncio
    async def test_the_brand_name_carries_its_colour_in_a_span(self, correo):
        for nombre, cuerpo in (await _los_cinco(correo)).items():
            marcas = [n for n in _nodos(cuerpo, "span") if n.texto == "RyderCupFriends"]
            assert len(marcas) == 1, nombre
            assert marcas[0].estilo == f"color:{BLANCO};", nombre
            celda = marcas[0].padre
            assert celda.etiqueta == "td", nombre
            assert not celda.texto.strip(), nombre
            assert any(_fondo(a) == VERDE for a in marcas[0].ancestros()), nombre

    @pytest.mark.asyncio
    async def test_no_paragraph_sits_inside_another(self, correo):
        for nombre, cuerpo in (await _los_cinco(correo)).items():
            for p in _nodos(cuerpo, "p"):
                assert all(a.etiqueta != "p" for a in p.ancestros()), nombre

    @pytest.mark.asyncio
    async def test_the_fallback_link_is_the_primary_buttons_link(self, correo):
        for nombre, cuerpo in (await _los_cinco(correo)).items():
            principal = _anclas_de_boton(cuerpo)[0].attrs["href"]
            respaldo = [p for p in _nodos(cuerpo, "p") if "¿No funciona el botón?" in p.texto]
            assert len(respaldo) == 1, nombre
            enlaces = [n for n in respaldo[0].todos() if n.etiqueta == "a"]
            assert len(enlaces) == 1, nombre
            assert enlaces[0].attrs["href"] == principal, nombre
            assert enlaces[0].texto == principal, nombre


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


class TestTheHandicapsPendingEmail:
    """El aviso al organizador de hándicaps sin actualizar con la RFEG (#251)."""

    @pytest.mark.asyncio
    async def test_it_opens_the_competition_and_names_who_is_pending(self, correo):
        await correo.send_handicaps_pending_email(
            "org@b.com", "Ana", "Medal de octubre", "c-1", ["Luis Pérez", "Eva Gil"]
        )
        destinatario, asunto, texto, cuerpo = _enviado(correo)
        assert destinatario == '"Ana" <org@b.com>'
        assert "Medal de octubre" in asunto
        assert _botones(cuerpo)[0] == f"{WEB}/competitions/c-1"
        assert f"{WEB}/competitions/c-1" in texto
        for nombre in ("Luis Pérez", "Eva Gil"):
            assert nombre in cuerpo and nombre in texto

    @pytest.mark.asyncio
    async def test_player_names_are_escaped(self, correo):
        await correo.send_handicaps_pending_email(
            "org@b.com", "Ana", "Copa & Cena", "c-1", ["<b>Luis</b>"]
        )
        _, _, _, cuerpo = _enviado(correo)
        assert "<b>Luis</b>" not in cuerpo
        assert "Copa &amp; Cena" in cuerpo

    @pytest.mark.asyncio
    async def test_it_does_not_say_it_was_the_close(self, correo):
        """También la manda una actualización con el botón: no siempre fue al cerrar (#251)."""
        await correo.send_handicaps_pending_email("org@b.com", "Ana", "Copa", "c-1", ["Luis"])
        _, _, texto, cuerpo = _enviado(correo)
        for contenido in (texto, cuerpo):
            assert "cerrar las inscripciones" not in contenido
            assert "enrollments closed" not in contenido


class TestTheScheduledUpdateSkippedEmail:
    """La programada no se lanzó: a su hora la ventana estaba cerrada (#251)."""

    @pytest.mark.asyncio
    async def test_it_says_why_and_opens_the_competition(self, correo):
        await correo.send_scheduled_handicaps_update_skipped_email(
            "org@b.com", "Ana", "Medal de octubre", "c-1", "Hay una jornada en marcha."
        )
        destinatario, asunto, texto, cuerpo = _enviado(correo)
        assert destinatario == '"Ana" <org@b.com>'
        assert "Medal de octubre" in asunto
        assert "Hay una jornada en marcha." in cuerpo and "Hay una jornada en marcha." in texto
        assert _botones(cuerpo)[0] == f"{WEB}/competitions/c-1"

    @pytest.mark.asyncio
    async def test_the_reason_is_escaped(self, correo):
        await correo.send_scheduled_handicaps_update_skipped_email(
            "org@b.com", "Ana", "Copa", "c-1", "<b>x</b>"
        )
        _, _, _, cuerpo = _enviado(correo)
        assert "<b>x</b>" not in cuerpo
