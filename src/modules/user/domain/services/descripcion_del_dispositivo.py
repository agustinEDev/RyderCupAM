"""
Qué dispositivo es, a partir de su user-agent (BE #737).

Tres códigos que el front traduce: el tipo (para el icono), la plataforma y el
navegador. Se calcula al leer, no se guarda: si se afina el reconocimiento, los
dispositivos de antes salen bien sin migrar nada.
"""

import ipaddress
from dataclasses import dataclass

DESCONOCIDO = "unknown"


@dataclass(frozen=True)
class DescripcionDelDispositivo:
    """Tipo (phone, tablet, computer), plataforma y navegador, o «unknown»."""

    tipo: str
    plataforma: str
    navegador: str


_NADA = DescripcionDelDispositivo(DESCONOCIDO, DESCONOCIDO, DESCONOCIDO)

# El navegador, en este orden: los integrados en apps antes que el motor que usan,
# y los derivados de Chrome antes que Chrome (Edge, Opera y Samsung lo llevan dentro)
_NAVEGADORES = (
    ("instagram", ("Instagram",)),
    ("facebook", ("FBAN/", "FBAV/", "FB_IAB")),
    ("google", ("GSA/",)),
    ("edge", ("EdgiOS/", "EdgA/", "Edg/", "Edge/")),
    ("opera", ("OPR/", "OPiOS/", "Opera")),
    ("samsung", ("SamsungBrowser/",)),
    ("chrome", ("CriOS/", "Chrome/")),
    ("firefox", ("FxiOS/", "Firefox/")),
    ("safari", ("Safari/", "Version/")),
)


# La plataforma y el tipo, en este orden: el iPhone y el iPad antes que el Mac (los
# dos dicen «like Mac OS X»), y Android y ChromeOS antes que Linux
_PLATAFORMAS = (
    (("iPhone", "iPod"), "iphone", "phone"),
    (("iPad",), "ipad", "tablet"),
    (("Android",), "android", None),
    (("CrOS",), "chromebook", "computer"),
    (("Macintosh", "Mac OS X"), "mac", "computer"),
    (("Windows",), "windows", "computer"),
    (("Linux", "X11"), "linux", "computer"),
)


def _plataforma(ua: str) -> tuple[str, str] | None:
    """La plataforma y el tipo, o None si no es un navegador conocido."""
    for marcas, plataforma, tipo in _PLATAFORMAS:
        if any(marca in ua for marca in marcas):
            # Un Android sin «Mobile» es una tablet
            return plataforma, tipo or ("phone" if "Mobile" in ua else "tablet")
    return None


def describe_el_dispositivo(user_agent: str | None) -> DescripcionDelDispositivo:
    """Tipo, plataforma y navegador de un user-agent. No lanza: lo raro es «unknown»."""
    ua = (user_agent or "").strip()
    plataforma = _plataforma(ua) if ua else None
    if plataforma is None:
        return _NADA
    navegador = next(
        (nombre for nombre, marcas in _NAVEGADORES if any(marca in ua for marca in marcas)),
        DESCONOCIDO,
    )
    return DescripcionDelDispositivo(
        tipo=plataforma[1], plataforma=plataforma[0], navegador=navegador
    )


def ip_tapada(ip: str | None) -> str | None:
    """
    La IP para la pantalla, con el final tapado (BE #737).

    IPv4 sin su último número; IPv6 solo con su /64 (la red, sin el dispositivo).
    La completa se guarda para auditoría, pero no hace falta enseñarla. None si no
    es una IP real (vacía, la de relleno o basura).
    """
    try:
        direccion = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return None
    if direccion.is_unspecified:
        return None
    if isinstance(direccion, ipaddress.IPv4Address):
        return ".".join(str(direccion).split(".")[:3]) + ".***"
    grupos = direccion.exploded.split(":")[:4]
    return ":".join(format(int(g, 16), "x") for g in grupos) + ":****"
