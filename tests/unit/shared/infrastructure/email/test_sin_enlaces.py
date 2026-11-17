"""
Lo que escribe un usuario no sale como enlace en los correos de la app (SB-05).

Un jugador verificado podía llamar a su competición «Premio: entra en premio.com» o
escribirlo en el mensaje de la invitación, e invitar a cien direcciones por hora: el
correo sale del dominio de la app, con SPF y DKIM buenos, y el cliente de correo lo
convertía en un enlace pulsable. Decidido por Agustín el 17 nov 2026: lo que parezca
un enlace o un dominio se muestra como texto que no se puede pulsar.
"""

import pytest

from src.shared.infrastructure.email.sin_enlaces import desarma_enlaces


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("entra en https://premio.com/ya", "entra en https[:]//premio[.]com/ya"),
        ("http://x.es", "http[:]//x[.]es"),
        ("www.premio.com", "www[.]premio[.]com"),
        ("Premio en premio.com", "Premio en premio[.]com"),
        ("PREMIO.COM", "PREMIO[.]COM"),
        ("escribe a gana@premio.net", "escribe a gana@premio[.]net"),
        ("sub.dominio.premio.io/ruta?x=1", "sub[.]dominio[.]premio[.]io/ruta?x=1"),
        # Puntos que se parecen a un punto: los clientes los tratan como tal
        ("premio\u3002com", "premio[.]com"),
        ("premio\uff0ecom/regalo", "premio[.]com/regalo"),
        ("premio\uff61com", "premio[.]com"),
        # Caracteres invisibles dentro del dominio: fuera
        ("premio\u200b.com", "premio[.]com"),
        ("premio.c\u00adom", "premio[.]com"),
        # Una IP también lleva a un servidor
        ("en 203.0.113.7/regalo", "en 203[.]0[.]113[.]7/regalo"),
        ("http://203.0.113.7", "http[:]//203[.]0[.]113[.]7"),
        ("Entra en 203.0.113.7.", "Entra en 203[.]0[.]113[.]7."),
        # Un acento escrito aparte, que se junta con su letra antes de buscar
        ("cafe\u0301.fr", "caf\u00e9[.]fr"),
        # Dominios internacionales y en punycode
        ("Gana en пример.рф", "Gana en пример[.]рф"),
        ("premio.xn--p1ai/ya", "premio[.]xn--p1ai/ya"),
        # Esquemas sin «//»: llamadas y mensajes de pago
        ("Llama ya: tel:+34600000000", "Llama ya: tel[:]+34600000000"),
        ("sms:+34600000000?body=x", "sms[:]+34600000000?body=x"),
        ("mailto:gana@premio.com", "mailto[:]gana@premio[.]com"),
    ],
)
def test_links_and_domains_cannot_be_clicked(texto, esperado):
    """
    Given: Un texto de usuario con un enlace o un dominio
    When: Se prepara para un correo
    Then: Los puntos y el «://» van entre corchetes: se lee, pero no se puede pulsar
    """
    assert desarma_enlaces(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "Ryder Cup de los amigos",
        "Torneo 2026.1",
        "J.R. Martín",
        "Sr. Pérez",
        "Club de Golf La Herrería",
        "",
    ],
)
def test_ordinary_text_is_left_alone(texto):
    """
    Given: Nombres y textos normales, también con puntos
    When: Se preparan para un correo
    Then: No cambian
    """
    assert desarma_enlaces(texto) == texto
