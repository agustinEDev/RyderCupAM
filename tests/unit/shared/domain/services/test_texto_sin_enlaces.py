"""
El detector de enlaces de lo que escribe un usuario (SB-05, decidido el 17 nov 2026).

Lo que un cliente de correo convertiría en un enlace no se deja escribir en el nombre de
una competición, en un alias ni en el mensaje de una invitación.
"""

import pytest

from src.shared.domain.services.texto_sin_enlaces import contiene_enlace


@pytest.mark.parametrize(
    "texto",
    [
        "entra en https://premio.com/ya",
        "http://x.es",
        "www.premio.com",
        "Premio en premio.com",
        "PREMIO.COM",
        "escribe a gana@premio.net",
        "sub.dominio.premio.io/ruta?x=1",
        "premio\u3002com",
        "premio\uff0ecom/regalo",
        "premio\uff61com",
        "premio\u200b.com",
        "premio.c\u00adom",
        "en 203.0.113.7/regalo",
        "http://203.0.113.7",
        "Entra en 203.0.113.7.",
        "cafe\u0301.fr",
        "Gana en пример.рф",
        "premio.xn--p1ai/ya",
        "Llama ya: tel:+34600000000",
        "sms:+34600000000?body=x",
        "mailto:gana@premio.com",
        "premio.cat",
        "premio.eus",
        "www.premio.bet",
        "gana@premio.lat",
        "premio\u200e.com",
        "premio\u2063.com",
        "Club.golf",
    ],
)
def test_links_domains_ips_and_call_schemes_are_detected(texto):
    """
    Given: Un texto con un enlace, un dominio, una IP o un «tel:»
    When: Se mira si lleva enlace
    Then: Sí
    """
    assert contiene_enlace(texto) is True


@pytest.mark.parametrize(
    "texto",
    [
        "Ryder Cup de los amigos",
        "Torneo 2026.1",
        "J.R. Martín",
        "Sr. Pérez",
        "Club de Golf La Herrería",
        "",
        "j.garcia",
        "Ana.Maria",
        "Copa St.Andrews",
        "Hola Juan.Te invito",
        "Nos vemos el sabado.Un abrazo",
        "Copa Pro.Am 2026",
        "Torneo Ed.II",
        "Pepe.Jr",
        "Dr.No",
        "Club.Golf",
        None,
    ],
)
def test_ordinary_text_is_not_a_link(texto):
    """
    Given: Nombres y textos normales, también con puntos
    When: Se mira si lleva enlace
    Then: No
    """
    assert contiene_enlace(texto) is False
