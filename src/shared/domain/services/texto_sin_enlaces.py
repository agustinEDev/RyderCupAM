"""
Si un texto que escribe un usuario lleva un enlace o una dirección web (SB-05).

El nombre de una competición, el alias de una persona y el mensaje de una invitación
salen en correos que firma la app (SPF y DKIM buenos). Con un «entra en premio.com»
ahí, el cliente de correo lo convertía en un enlace pulsable: phishing con la firma de
la app. Decidido por Agustín el 17 nov 2026: no se dejan escribir (se avisa en el
formulario y no se guarda), en vez de desarmarlos en el correo, que dejaba corchetes
raros a la vista. Los nombres y apellidos ya no admiten puntos ni barras.

Cuenta como enlace, siempre: un esquema con «://», los de llamar o escribir sin él
(«tel:», «sms:», «mailto:»…), lo que empieza por «www.», una dirección de correo y una
IPv4. Y «algo.terminación» si la terminación existe (la lista de la IANA, en
`terminaciones_de_dominio`). Escrita «Mayúscula+minúsculas» es como empieza una frase sin
espacio tras el punto o un nombre («Juan.Te invito», «Copa Pro.Am»), así que entonces
solo cuenta si es de las habituales («premio.Com») o le sigue una ruta («premio.Golf/x»).
Decidido por Agustín el 17 nov 2026. Antes de buscar, fuera todos los caracteres de
formato (invisibles), el texto se normaliza a NFC y los puntos que se parecen a un punto
pasan a ser un punto: los detectores de enlaces de los clientes los leen así.

Coste: la búsqueda crece con el cuadrado de la longitud; los tres textos tienen tope
(100, 50 y 500 caracteres), así que no se debe usar con textos sin tope.
"""

import re
import unicodedata

from src.shared.domain.services.terminaciones_de_dominio import TERMINACIONES_DE_DOMINIO

# Puntos de otros alfabetos que los detectores de enlaces leen como un punto (UTS-46)
_PUNTOS = str.maketrans({"\u3002": ".", "\uff0e": ".", "\uff61": "."})

# Lo que es enlace sin mirar más
_ESQUEMA = re.compile(r"[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_ESQUEMA_SIN_BARRAS = re.compile(
    r"(?<![a-z])(?:tel|sms|mailto|callto|whatsapp):(?!//)", re.IGNORECASE
)
_WWW = re.compile(r"(?<![a-z0-9])www\.[^\s.]", re.IGNORECASE)
_CORREO = re.compile(r"[^\s@]+@[^\s@.]+\.[^\s@]+")
# Al final de una frase puede seguir un punto: lo que no puede seguir es otro número
_IP = re.compile(r"(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9]|\.[0-9])")


_ULTIMO_PUNTO_DE_UNICODE = 0x10FFFF


def _clase_de_marcas() -> str:
    """
    Las marcas que se combinan (Unicode M*), como clase de regex. `\\w` no las incluye y
    van dentro de las palabras de muchos alfabetos: el signo de la «ा» de «भारत».
    """
    rangos: list[tuple[int, int]] = []
    for punto in range(_ULTIMO_PUNTO_DE_UNICODE + 1):
        if unicodedata.category(chr(punto)).startswith("M"):
            if rangos and rangos[-1][1] == punto - 1:
                rangos[-1] = (rangos[-1][0], punto)
            else:
                rangos.append((punto, punto))
    return "".join(f"\\U{a:08x}-\\U{b:08x}" for a, b in rangos)


_MARCAS = _clase_de_marcas()

# «algo.algo»: etiquetas de letras y números (con sus marcas) y guiones dentro, y una
# última de letras (o punycode). Si es dominio lo decide la terminación, en
# `_es_terminacion`
_ETIQUETA = rf"[^\W_](?:[\w{_MARCAS}-]{{0,61}}(?:[^\W_]|[{_MARCAS}]))?"
_DOMINIO = re.compile(
    rf"(?<![\w{_MARCAS}-])(?:{_ETIQUETA}\.)+"
    rf"([^\W\d_](?:[^\W\d_]|[{_MARCAS}]){{1,62}}|xn--[a-z0-9-]{{1,59}})(?![\w{_MARCAS}-])",
    re.IGNORECASE,
)

# Las que se escriben con mayúscula inicial sin dejar de ser una dirección: las
# habituales. Las demás, así escritas, se leen como palabra («Juan.Te», «Pro.Am»)
_HABITUALES = frozenset(
    [
        "com",
        "net",
        "org",
        "es",
        "eu",
        "info",
        "io",
        "app",
        "me",
        "biz",
        "co",
        "xyz",
        "online",
        "site",
        "shop",
        "club",
        "top",
        "link",
        "click",
        "live",
        "store",
        "uk",
        "de",
        "fr",
        "it",
        "pt",
        "us",
        "ai",
        "dev",
        "tv",
        "ly",
        "gg",
        "cat",
    ]
)


def _sin_invisibles(texto: str) -> str:
    """Fuera los caracteres de formato (Cf): de anchura cero, de dirección, guion blando…"""
    return "".join(c for c in texto if unicodedata.category(c) != "Cf")


def _es_terminacion(final: str, sigue: str) -> bool:
    """
    Si la última etiqueta es una terminación de dominio, escrita como dirección.

    Args:
        final: La última etiqueta («com», «Te», «рф»)
        sigue: El carácter que va detrás («/» si sigue una ruta; vacío al final)
    """
    # «Te», «Am», «Golf»: una palabra que empieza frase o nombre, salvo que sea una
    # terminación habitual o le siga una ruta
    if (
        len(final) > 1
        and final[0].isupper()
        and final[1:].islower()
        and final.lower() not in _HABITUALES
        and sigue != "/"
    ):
        return False
    if final.isascii():
        return final.lower() in TERMINACIONES_DE_DOMINIO
    # Otro alfabeto («рф»): la IANA la lista en punycode
    try:
        return "xn--" + final.lower().encode("punycode").decode() in TERMINACIONES_DE_DOMINIO
    except UnicodeError:
        return False


def contiene_enlace(texto: str | None) -> bool:
    """
    Si el texto lleva algo que un cliente de correo convertiría en un enlace.

    Args:
        texto: Lo que escribió un usuario (un nombre, un alias, un mensaje)

    Returns:
        True si lleva un esquema, «www.», un correo, una IP o un dominio
    """
    if not texto:
        return False
    # Primero fuera los invisibles: quitarlos después de normalizar podría dejar una
    # letra y su marca sin juntar
    limpio = unicodedata.normalize("NFC", _sin_invisibles(texto)).translate(_PUNTOS)
    if any(p.search(limpio) for p in (_ESQUEMA, _ESQUEMA_SIN_BARRAS, _WWW, _CORREO, _IP)):
        return True
    return any(
        _es_terminacion(m.group(1), limpio[m.end() : m.end() + 1])
        for m in _DOMINIO.finditer(limpio)
    )
