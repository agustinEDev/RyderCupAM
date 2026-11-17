"""
Lo que escribe un usuario no sale como enlace en un correo de la app (SB-05).

El nombre de una competición, el de quien invita o el mensaje de una invitación los
escribe un usuario, y el correo sale del dominio de la app con SPF y DKIM buenos. Si
ahí pone «entra en premio.com», el cliente de correo lo convertía en un enlace
pulsable: phishing con la firma de la app. Decidido por Agustín el 17 nov 2026: lo que
parezca un enlace o un dominio se muestra como texto que no se puede pulsar.

Se «desarma» como hacen los equipos de seguridad: los puntos del dominio y los dos
puntos del esquema van entre corchetes («premio[.]com», «https[:]//», «tel[:]»). Se
sigue leyendo, y ningún cliente lo reconoce como enlace. El escapado del HTML va
aparte (`email_layout`): esto no lo sustituye.

Antes de buscar, los puntos que se parecen a un punto (el ideográfico U+3002 y los de
anchura completa U+FF0E y U+FF61) pasan a ser un punto y se quitan los caracteres
invisibles (de anchura cero, guion blando): los clientes los ignoran o los tratan como
un punto al detectar enlaces, y si no, se colaría un dominio escrito con ellos.

Coste: el texto de un usuario llega con tope de longitud (el mensaje, 500 caracteres);
la búsqueda crece con el cuadrado de la longitud, así que no se debe usar con textos
sin tope.
"""

import re
import unicodedata

# Puntos de otros alfabetos que los detectores de enlaces leen como un punto (UTS-46)
_PUNTOS = str.maketrans({"\u3002": ".", "\uff0e": ".", "\uff61": "."})
# Invisibles: de anchura cero, unión de palabras, marca de orden, guion blando
_INVISIBLES = re.compile("[\u200b-\u200d\u2060\ufeff\u00ad]")

# Una etiqueta de dominio: letras (de cualquier alfabeto) y números, con guiones dentro
_ETIQUETA = r"[^\W_](?:[\w-]{0,61}[^\W_])?"
# Un dominio: etiquetas separadas por puntos que acaban en una de solo letras (2 a 63),
# o en punycode («xn--…»). «2026.1» o «J.R.» no lo son; «premio.com», «пример.рф» sí
_DOMINIO = re.compile(
    rf"(?<![\w-])(?:{_ETIQUETA}\.)+(?:[^\W\d_]{{2,63}}|xn--[a-z0-9-]{{1,59}})(?![\w-])",
    re.IGNORECASE,
)
# Una dirección IPv4: también lleva a un servidor, sin dominio
# Al final de una frase puede seguir un punto: lo que no puede seguir es otro número
_IP = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?!\d|\.\d)")
# Un esquema con «//» (https://, ftp://…) o de los que abren algo sin él
_ESQUEMA = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*)://")
_ESQUEMA_SIN_BARRAS = re.compile(r"(?i)\b(tel|sms|mailto|callto|whatsapp):(?!//)")


def desarma_enlaces(texto: str) -> str:
    """
    El texto con sus enlaces y dominios desarmados.

    Args:
        texto: Lo que escribió un usuario (un nombre, un mensaje)

    Returns:
        El mismo texto, con «://» como «[:]//», «tel:» como «tel[:]» y los puntos de
        cada dominio o IP como «[.]»
    """
    if not texto:
        return texto
    # NFC primero: un dominio con el acento aparte («e» + U+0301) no casaba (CodeRabbit)
    limpio = unicodedata.normalize("NFC", texto)
    limpio = _INVISIBLES.sub("", limpio.translate(_PUNTOS))
    limpio = _ESQUEMA.sub(lambda m: f"{m.group(1)}[:]//", limpio)
    limpio = _ESQUEMA_SIN_BARRAS.sub(lambda m: f"{m.group(1)}[:]", limpio)
    limpio = _IP.sub(lambda m: m.group(0).replace(".", "[.]"), limpio)
    return _DOMINIO.sub(lambda m: m.group(0).replace(".", "[.]"), limpio)
