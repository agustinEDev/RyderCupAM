"""
Lo que escribe un usuario no sale como enlace en un correo de la app (SB-05).

El nombre de una competición, el de quien invita o el mensaje de una invitación los
escribe un usuario, y el correo sale del dominio de la app con SPF y DKIM buenos. Si
ahí pone «entra en premio.com», el cliente de correo lo convertía en un enlace
pulsable: phishing con la firma de la app. Decidido por Agustín el 17 nov 2026: lo que
parezca un enlace o un dominio se muestra como texto que no se puede pulsar.

Se «desarma» como hacen los equipos de seguridad: los puntos del dominio y el «://» van
entre corchetes («premio[.]com»). Se sigue leyendo, y ningún cliente lo reconoce como
enlace. El escapado del HTML va aparte (`email_layout`): esto no lo sustituye.
"""

import re

# Un dominio: etiquetas de letras, números y guiones separadas por puntos, que acaban en
# una de solo letras (de 2 a 63, como un dominio de primer nivel). «2026.1» o «J.R.» no
# lo son; «premio.com» y «sub.premio.io» sí. Solo ASCII: un nombre con tildes no es un
# dominio que un cliente de correo vaya a convertir en enlace
_DOMINIO = re.compile(
    r"(?<![A-Za-z0-9-])"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}"
    r"(?![A-Za-z0-9-])"
)
_ESQUEMA = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*)://")


def desarma_enlaces(texto: str) -> str:
    """
    El texto con sus enlaces y dominios desarmados.

    Args:
        texto: Lo que escribió un usuario (un nombre, un mensaje)

    Returns:
        El mismo texto, con «://» como «[:]//» y los puntos de cada dominio como «[.]»
    """
    if not texto:
        return texto
    sin_esquema = _ESQUEMA.sub(lambda m: f"{m.group(1)}[:]//", texto)
    return _DOMINIO.sub(lambda m: m.group(0).replace(".", "[.]"), sin_esquema)
