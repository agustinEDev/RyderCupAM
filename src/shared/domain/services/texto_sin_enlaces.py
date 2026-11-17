"""
Si un texto que escribe un usuario lleva un enlace o una dirección web (SB-05).

El nombre de una competición, el alias de una persona y el mensaje de una invitación
salen en correos que firma la app (SPF y DKIM buenos). Con un «entra en premio.com»
ahí, el cliente de correo lo convertía en un enlace pulsable: phishing con la firma de
la app. Decidido por Agustín el 17 nov 2026: no se dejan escribir (se avisa en el
formulario y no se guarda), en vez de desarmarlos en el correo, que dejaba corchetes
raros a la vista. Los nombres y apellidos ya no admiten puntos ni barras.

Cuenta como enlace: un esquema con «://», los de llamar o escribir sin él («tel:»,
«sms:», «mailto:»…), una dirección IPv4 y cualquier dominio («premio.com»,
«пример.рф», «xn--…»). Antes de buscar, el texto se normaliza a NFC, los puntos que se
parecen a un punto pasan a ser un punto y fuera los caracteres invisibles: los
detectores de enlaces de los clientes los leen así.

Coste: la búsqueda crece con el cuadrado de la longitud; los tres textos tienen tope
(100, 50 y 500 caracteres), así que no se debe usar con textos sin tope.
"""

import re
import unicodedata

# Puntos de otros alfabetos que los detectores de enlaces leen como un punto (UTS-46)
_PUNTOS = str.maketrans({"\u3002": ".", "\uff0e": ".", "\uff61": "."})
# Invisibles: de anchura cero, unión de palabras, marca de orden, guion blando
_INVISIBLES = re.compile("[\u200b-\u200d\u2060\ufeff\u00ad]")

# Una etiqueta de dominio: letras (de cualquier alfabeto) y números, con guiones dentro
_ETIQUETA = r"[^\W_](?:[\w-]{0,61}[^\W_])?"
# Las terminaciones que un cliente de correo convierte en enlace: las de dos letras (los
# países: .es, .io, .ly…), las genéricas de siempre y las nuevas que más usa el spam.
# No cualquier palabra: «j.garcia» o «Ana.Maria» son alias, no dominios (falsos
# positivos que rechazaban alias normales)
_TERMINACIONES = (
    "com|net|org|info|biz|edu|gov|mil|int|name|pro|mobi|app|dev|page|io|ai|co|me|tv|"
    "xyz|top|site|online|shop|store|club|link|click|live|life|world|today|news|blog|"
    "cloud|tech|fun|icu|vip|win|bid|loan|work|space|website|email|support|help|"
    "login|secure|bank|money|pay|wallet|crypto|golf|gift|deals|sale|promo"
)
# Un dominio: etiquetas separadas por puntos que acaban en una terminación de las de
# arriba, en dos letras, en letras de otro alfabeto («пример.рф») o en punycode
_DOMINIO = re.compile(
    rf"(?<![\w-])(?:{_ETIQUETA}\.)+"
    rf"(?:{_TERMINACIONES}|[a-z]{{2}}|[^\W\da-z_]{{2,63}}|xn--[a-z0-9-]{{1,59}})"
    r"(?![\w-])",
    re.IGNORECASE,
)
# Una dirección IPv4: también lleva a un servidor, sin dominio
# Al final de una frase puede seguir un punto: lo que no puede seguir es otro número
_IP = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?!\d|\.\d)")
# Un esquema con «//» (https://, ftp://…) o de los que abren algo sin él
_ESQUEMA = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*)://")
_ESQUEMA_SIN_BARRAS = re.compile(r"(?i)\b(tel|sms|mailto|callto|whatsapp):(?!//)")


def contiene_enlace(texto: str | None) -> bool:
    """
    Si el texto lleva algo que un cliente de correo convertiría en un enlace.

    Args:
        texto: Lo que escribió un usuario (un nombre, un alias, un mensaje)

    Returns:
        True si lleva un esquema, una IP o un dominio
    """
    if not texto:
        return False
    limpio = unicodedata.normalize("NFC", texto)
    limpio = _INVISIBLES.sub("", limpio.translate(_PUNTOS))
    return any(patron.search(limpio) for patron in (_ESQUEMA, _ESQUEMA_SIN_BARRAS, _IP, _DOMINIO))
