"""
La plantilla común de los correos (BE #389).

Los cinco correos de la aplicación comparten esta cara: cabecera verde con el
monograma, un título que dice lo que pasa, un único botón grande y un pie
común. El español va primero y completo; el inglés, debajo y más corto, con
su propio botón.

**Hecha para clientes de correo, no para navegadores.** Tablas y estilos en
línea: Gmail borra los bloques <style>, y Outlook no entiende flex ni grid.

**Nada del usuario entra como HTML.** Cada pieza escapa el texto que recibe;
solo `Html` —lo que la propia plantilla ya ha construido— pasa tal cual. Así
un nombre con «&» o un mensaje con «<script>» no pueden romper el correo ni
colarse en él, se escriba el correo que se escriba.
"""

import html as _html
from dataclasses import dataclass
from datetime import UTC, datetime

VERDE = "#15803d"
VERDE_OSCURO = "#14532d"
FONDO = "#eef2ee"
TEXTO = "#374151"
TITULAR = "#111827"
APAGADO = "#6b7280"
_LETRA = "Inter, Arial, Helvetica, sans-serif"
_LETRA_TITULO = "Poppins, Arial, Helvetica, sans-serif"


class Html(str):
    """Fragmento ya construido por la plantilla: no se vuelve a escapar."""


def _seguro(texto: str) -> str:
    return texto if isinstance(texto, Html) else _html.escape(texto)


def negrita(texto: str) -> Html:
    return Html(f"<strong>{_seguro(texto)}</strong>")


def frase(*partes: str) -> Html:
    """Une trozos de una frase: el texto se escapa, lo marcado como Html no."""
    return Html("".join(_seguro(p) for p in partes))


@dataclass(frozen=True)
class Boton:
    texto: str
    enlace: str


def parrafo(*partes: str, pequeno: bool = False) -> Html:
    tamano = "13px" if pequeno else "15px"
    color = APAGADO if pequeno else TEXTO
    return Html(
        f'<p style="margin:0 0 14px;font-family:{_LETRA};font-size:{tamano};'
        f'line-height:1.6;color:{color};">{frase(*partes)}</p>'
    )


def recuadro(titulo: str, *lineas: str) -> Html:
    """Lo importante del correo —la competición, el plazo— en su caja."""
    filas = "".join(
        f'<div style="font-family:{_LETRA};font-size:13px;line-height:1.5;color:#4b5563;">'
        f"{_seguro(linea)}</div>"
        for linea in lineas
    )
    return Html(
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="margin:0 0 14px;border-collapse:separate;">'
        '<tr><td style="background:#f0faf3;border:1px solid #bbe5c8;border-radius:10px;'
        'padding:14px 16px;">'
        f'<div style="font-family:{_LETRA_TITULO};font-size:17px;font-weight:700;'
        f'line-height:1.3;color:{VERDE_OSCURO};">{_seguro(titulo)}</div>'
        f"{filas}</td></tr></table>"
    )


def cita(texto: str, autor: str) -> Html:
    """El mensaje personal de quien invita."""
    return Html(
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" data-cita '
        'style="margin:0 0 14px;"><tr><td style="background:#f6f7f6;border-radius:10px;'
        'padding:12px 16px;">'
        f'<div style="font-family:{_LETRA};font-size:14px;font-style:italic;line-height:1.55;'
        f'color:{TEXTO};">«{_seguro(texto)}»</div>'
        f'<div style="font-family:{_LETRA};font-size:12px;color:{APAGADO};margin-top:4px;">'
        f"{_seguro(autor)}</div></td></tr></table>"
    )


def aviso(*partes: str) -> Html:
    """Algo que requiere atención —«¿no has sido tú?»—, en ámbar."""
    return Html(
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="margin:0 0 14px;"><tr><td style="background:#fff7ed;border:1px solid #fed7aa;'
        f"border-radius:10px;padding:12px 16px;font-family:{_LETRA};font-size:14px;"
        f'line-height:1.55;color:#7c2d12;">{frase(*partes)}</td></tr></table>'
    )


def _boton(boton: Boton, principal: bool) -> str:
    if principal:
        estilo = (
            f"background:{VERDE};color:#ffffff;border:2px solid {VERDE};"
            "font-size:15px;padding:13px 18px;"
        )
    else:
        estilo = (
            f"background:#ffffff;color:{VERDE};border:2px solid {VERDE};"
            "font-size:14px;padding:10px 16px;"
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="margin:4px 0 14px;"><tr><td align="center">'
        f'<a data-boton href="{_html.escape(boton.enlace, quote=True)}" '
        f'style="display:block;{estilo}border-radius:10px;font-family:{_LETRA};'
        f'font-weight:700;text-align:center;text-decoration:none;">'
        f"{_seguro(boton.texto)}</a></td></tr></table>"
    )


def _respaldo(enlace: str) -> str:
    """El enlace a mano, por si el botón no se puede pulsar."""
    seguro = _html.escape(enlace, quote=True)
    return (
        f'<p style="margin:0 0 6px;font-family:{_LETRA};font-size:12px;line-height:1.5;'
        f'color:{APAGADO};">¿No funciona el botón? Copia este enlace · '
        f"Button not working? Copy this link:<br>"
        f'<a href="{seguro}" style="color:{VERDE};word-break:break-all;">{seguro}</a></p>'
    )


@dataclass(frozen=True)
class Ingles:
    """El bloque en inglés: una frase y su botón."""

    texto: Html
    boton: Boton


def correo(
    *,
    web: str,
    resumen: str,
    etiqueta: str,
    titulo: str,
    cuerpo: list[Html],
    boton: Boton,
    ingles: Ingles,
    pie: str,
    otros_botones: list[Boton] | None = None,
    con_respaldo: bool = False,
) -> str:
    """
    Arma el correo entero.

    Args:
        web: La dirección del frontend, de donde sale el logo
        resumen: La línea que el cliente de correo enseña junto al asunto
        etiqueta: La palabra de encima del título («Invitación»)
        titulo: Lo que pasa, en una frase
        cuerpo: Los párrafos y cajas del español, ya construidos
        boton: La acción principal
        ingles: El bloque corto en inglés
        pie: Por qué le llega el correo, en los dos idiomas
        otros_botones: Acciones secundarias bajo la principal (registrarse)
        con_respaldo: Si se repite el enlace a mano bajo el botón
    """
    logo = _html.escape(f"{web}/images/rcf-monogram-white.png", quote=True)
    anio = datetime.now(UTC).year
    secundarios = "".join(_boton(b, principal=False) for b in otros_botones or [])
    respaldo = _respaldo(boton.enlace) if con_respaldo else ""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{_seguro(titulo)}</title>
</head>
<body style="margin:0;padding:0;background:{FONDO};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{_seguro(resumen)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{FONDO};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:12px;overflow:hidden;">
<tr><td style="background:{VERDE};padding:18px 24px;">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td style="padding-right:12px;"><img src="{logo}" width="40" alt="RCF" style="display:block;width:40px;height:auto;border:0;"></td>
<td style="font-family:{_LETRA_TITULO};font-size:17px;font-weight:700;color:#ffffff;">RyderCupFriends</td>
</tr></table>
</td></tr>
<tr><td style="padding:28px 24px 4px;">
<div style="font-family:{_LETRA};font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:{VERDE};margin:0 0 8px;">{_seguro(etiqueta)}</div>
<h1 style="margin:0 0 14px;font-family:{_LETRA_TITULO};font-size:22px;line-height:1.25;color:{TITULAR};">{_seguro(titulo)}</h1>
{"".join(cuerpo)}
{_boton(boton, principal=True)}
{secundarios}
{respaldo}
</td></tr>
<tr><td style="padding:4px 24px 0;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="border-top:1px solid #e5e7eb;padding-top:16px;">
<div style="font-family:{_LETRA};font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:{APAGADO};margin:0 0 8px;">English</div>
<p style="margin:0 0 10px;font-family:{_LETRA};font-size:14px;line-height:1.55;color:#4b5563;">{ingles.texto}</p>
{_boton(ingles.boton, principal=False)}
</td></tr></table>
</td></tr>
<tr><td style="background:#f8faf8;border-top:1px solid #eef1ee;padding:18px 24px 22px;font-family:{_LETRA};font-size:12px;line-height:1.5;color:{APAGADO};">
{_seguro(pie)}<br>© {anio} RyderCupFriends
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""
