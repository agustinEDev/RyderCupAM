"""
El access token sale solo de la cookie httpOnly (F-03, release 2.58.0).

`read_access_token` es la única regla de dónde viene el token: la usan
get_current_user, el rate limit, el CSRF y Sentry. Desde la 2.58.0 la cabecera
Authorization: Bearer ya no cuenta.
"""

from starlette.requests import Request

from src.shared.infrastructure.security.cookie_handler import read_access_token


def _request(cookie: str | None = None, bearer: str | None = None) -> Request:
    """Una petición con la cookie de acceso, la cabecera Bearer, las dos o ninguna."""
    headers: list[tuple[bytes, bytes]] = []
    if cookie:
        headers.append((b"cookie", f"access_token={cookie}".encode()))
    if bearer:
        headers.append((b"authorization", f"Bearer {bearer}".encode()))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def test_only_a_bearer_header_is_no_token():
    """
    Given: Solo la cabecera Authorization: Bearer
    When: Se lee el access token
    Then: No hay ninguno
    """
    assert read_access_token(_request(bearer="token-de-cabecera")) is None


def test_the_cookie_is_the_token_even_with_a_bearer_header():
    """
    Given: La cookie y una cabecera Bearer distinta
    When: Se lee el access token
    Then: Es el de la cookie
    """
    assert read_access_token(_request(cookie="de-la-cookie", bearer="otro")) == "de-la-cookie"


def test_without_cookie_or_header_there_is_no_token():
    """
    Given: Una petición sin cookie ni cabecera
    When: Se lee el access token
    Then: No hay ninguno
    """
    assert read_access_token(_request()) is None
