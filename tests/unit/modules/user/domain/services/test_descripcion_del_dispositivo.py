"""
Qué dispositivo es, a partir de su user-agent (BE #737).

El nombre de antes se equivocaba mucho: Chrome, Firefox, Instagram o la app de
Google en el iPhone salían «Safari on iOS», un iPad «Safari on macOS», Opera como
Chrome en Windows y Samsung Internet como Chrome en Android. Ahora se describe con
tres códigos que el front traduce: tipo, plataforma y navegador.

  #    user-agent real                        | tipo     | plataforma | navegador
  -----|----------------------------------------|----------|------------|-----------
  U1   Safari en iPhone                       | phone    | iphone     | safari
  U2   Chrome en iPhone (CriOS)               | phone    | iphone     | chrome
  U3   Firefox en iPhone (FxiOS)              | phone    | iphone     | firefox
  U4   Edge en iPhone (EdgiOS)                | phone    | iphone     | edge
  U5   Instagram en iPhone                    | phone    | iphone     | instagram
  U6   app de Google en iPhone (GSA)          | phone    | iphone     | google
  U7   Facebook en iPhone (FBAN)              | phone    | iphone     | facebook
  U8   Safari en iPad                         | tablet   | ipad       | safari
  U9   Safari en Mac                          | computer | mac        | safari
  U10  Chrome en Mac                          | computer | mac        | chrome
  U11  Chrome en Android, móvil               | phone    | android    | chrome
  U12  Chrome en Android, tablet (sin Mobile) | tablet   | android    | chrome
  U13  Samsung Internet                       | phone    | android    | samsung
  U14  Chrome en Windows                      | computer | windows    | chrome
  U15  Edge en Windows                        | computer | windows    | edge
  U16  Opera en Windows                       | computer | windows    | opera
  U17  Firefox en Windows                     | computer | windows    | firefox
  U18  Chromebook                             | computer | chromebook | chrome
  U19  Firefox en Linux                       | computer | linux      | firefox
  U20  basura o vacío                         | unknown  | unknown    | unknown
"""

import pytest

from src.modules.user.domain.services.descripcion_del_dispositivo import describe_el_dispositivo

CASOS = [
    (
        "U1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
        "phone",
        "iphone",
        "safari",
    ),
    (
        "U2",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/130.0.6723.90 Mobile/15E148 Safari/604.1",
        "phone",
        "iphone",
        "chrome",
    ),
    (
        "U3",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/132.0 Mobile/15E148 Safari/605.1.15",
        "phone",
        "iphone",
        "firefox",
    ),
    (
        "U4",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 EdgiOS/130.2849.80 Mobile/15E148 Safari/605.1.15",
        "phone",
        "iphone",
        "edge",
    ),
    (
        "U5",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/22B83 Instagram 355.0.0.29.88 (iPhone15,2; iOS 18_1; es_ES; es)",
        "phone",
        "iphone",
        "instagram",
    ),
    (
        "U6",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) GSA/343.0.695551749 Mobile/15E148 Safari/604.1",
        "phone",
        "iphone",
        "google",
    ),
    (
        "U7",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/22B83 [FBAN/FBIOS;FBAV/490.0.0.45.98;FBBV/123]",
        "phone",
        "iphone",
        "facebook",
    ),
    (
        "U8",
        "Mozilla/5.0 (iPad; CPU OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
        "tablet",
        "ipad",
        "safari",
    ),
    (
        "U9",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
        "computer",
        "mac",
        "safari",
    ),
    (
        "U10",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "computer",
        "mac",
        "chrome",
    ),
    (
        "U11",
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
        "phone",
        "android",
        "chrome",
    ),
    (
        "U12",
        "Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "tablet",
        "android",
        "chrome",
    ),
    (
        "U13",
        "Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/26.0 Chrome/122.0.0.0 Mobile Safari/537.36",
        "phone",
        "android",
        "samsung",
    ),
    (
        "U14",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "computer",
        "windows",
        "chrome",
    ),
    (
        "U15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        "computer",
        "windows",
        "edge",
    ),
    (
        "U16",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 OPR/115.0.0.0",
        "computer",
        "windows",
        "opera",
    ),
    (
        "U17",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
        "computer",
        "windows",
        "firefox",
    ),
    (
        "U18",
        "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "computer",
        "chromebook",
        "chrome",
    ),
    (
        "U19",
        "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
        "computer",
        "linux",
        "firefox",
    ),
]


@pytest.mark.parametrize(
    ("caso", "ua", "tipo", "plataforma", "navegador"), CASOS, ids=[c[0] for c in CASOS]
)
def test_describe_the_device_from_a_real_user_agent(caso, ua, tipo, plataforma, navegador):
    """
    Given: Un user-agent real de cada caso de la cabecera
    When: Se describe el dispositivo
    Then: Tipo, plataforma y navegador son los de la tabla
    """
    descripcion = describe_el_dispositivo(ua)

    assert (descripcion.tipo, descripcion.plataforma, descripcion.navegador) == (
        tipo,
        plataforma,
        navegador,
    ), caso


@pytest.mark.parametrize("ua", ["", "   ", None, "curl/8.4.0", "basura sin forma"])
def test_describe_an_unknown_user_agent_without_raising(ua):
    """
    Given: Un user-agent vacío, de otro programa o basura
    When: Se describe
    Then: Todo «unknown», sin lanzar
    """
    descripcion = describe_el_dispositivo(ua)

    assert (descripcion.tipo, descripcion.plataforma, descripcion.navegador) == (
        "unknown",
        "unknown",
        "unknown",
    )


@pytest.mark.parametrize(
    ("ip", "tapada"),
    [
        ("90.71.66.47", "90.71.66.***"),
        ("2a09:bac2:3118:3632::566:60", "2a09:bac2:3118:3632:****"),
        ("2001:db8::1", "2001:db8:0:0:****"),
        ("0.0.0.0", None),
        ("", None),
        (None, None),
        ("no-es-una-ip", None),
    ],
)
def test_masked_ip_hides_the_end(ip, tapada):
    """
    Given: La IP de un dispositivo
    When: Se tapa para la pantalla
    Then: IPv4 sin el último número, IPv6 solo con su /64, y nada si no es una IP real
    """
    from src.modules.user.domain.services.descripcion_del_dispositivo import ip_tapada

    assert ip_tapada(ip) == tapada
