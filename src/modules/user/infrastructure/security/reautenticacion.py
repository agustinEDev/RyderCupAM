"""
La marca de «autenticado hace poco» para vincular Google (BE #753, punto 2).

Una cookie firmada, httpOnly, de 5 minutos y atada al usuario, solo para las rutas de
Google. La deja POST /auth/reauthenticate con la contraseña actual y la gasta
/auth/google/link al empezar: sirve una sola vez, también si el vínculo falla. Sin migración: lo gastado vive en memoria, como
el freno del login (un proceso; un reinicio solo deja usar otra vez una marca de menos
de 5 minutos).
"""

import threading
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Response

from src.config.settings import settings
from src.shared.infrastructure.security.cookie_handler import is_production

COOKIE = "reauth_token"
RUTA = "/api/v1/auth/google"
DURACION = timedelta(minutes=5)
_PROPOSITO = "google-link"

_gastadas: dict[str, datetime] = {}
_cerrojo = threading.Lock()


def emite(user_id: str, dura: timedelta = DURACION) -> str:
    """Una marca nueva para ese usuario."""
    ahora = datetime.now(UTC)
    datos = {
        "sub": user_id,
        "aud": _PROPOSITO,
        "jti": uuid.uuid4().hex,
        "iat": ahora,
        "exp": ahora + dura,
    }
    return jwt.encode(datos, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _lee(token: str | None, user_id: str) -> dict | None:
    """Los datos de una marca firmada, sin caducar, de ese usuario; si no, None."""
    if not token:
        return None
    try:
        datos = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], audience=_PROPOSITO
        )
    except jwt.InvalidTokenError:
        return None
    if datos.get("sub") != user_id or not datos.get("jti"):
        return None
    return datos


def gasta_si_vale(token: str | None, user_id: str) -> bool:
    """
    Si la marca es de ese usuario, no ha caducado y no se ha usado, la gasta y dice
    True. Comprobar y gastar van juntos bajo el cerrojo (code-review): en dos pasos, dos
    vínculos a la vez pasaban los dos. Lo gastado que haya caducado se olvida.
    """
    datos = _lee(token, user_id)
    if datos is None:
        return False
    ahora = datetime.now(UTC)
    with _cerrojo:
        if datos["jti"] in _gastadas:
            return False
        for jti in [j for j, hasta in _gastadas.items() if hasta < ahora]:
            del _gastadas[jti]
        _gastadas[datos["jti"]] = datetime.fromtimestamp(datos["exp"], UTC)
    return True


def pon_la_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE,
        value=token,
        max_age=int(DURACION.total_seconds()),
        path=RUTA,
        httponly=True,
        secure=is_production(),
        samesite="strict",
    )


def borra_la_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE, path=RUTA, httponly=True, secure=is_production(), samesite="strict"
    )
