"""
La cookie del dispositivo en las rutas del módulo de usuario (BE #737).

Lo que leen y escriben el login, el de Google, el refresco y verificar el email.
Vive en el módulo de usuario y no en `shared`: es una pieza de los dispositivos, y
la lectura en sí está en el dominio (`cookie_de_dispositivo`).
"""

from fastapi import Request, Response

from src.modules.user.domain.services.cookie_de_dispositivo import (
    SEPARADOR_DE_DISPOSITIVOS,
    ids_de_la_cookie_de_dispositivo,
    valor_de_la_cookie_de_dispositivo,
)
from src.shared.infrastructure.security.cookie_handler import (
    get_device_id_cookie_name,
    set_device_id_cookie,
)


def es_la_app_instalada(request: Request) -> bool:
    """Si la petición viene de la app instalada (PWA): la cabecera X-App-Mode (BE #737)."""
    return request.headers.get("X-App-Mode", "").strip().lower() == "standalone"


def ids_validos_de_la_cookie(valor: str | None) -> str | None:
    """
    Los ids válidos de la cookie del dispositivo, unidos por puntos, o None.

    La cookie la controla el cliente: se valida antes de pasar a los DTOs para no
    dar un 500 con un valor malformado (v2.0.4). Desde BE #737 guarda los
    dispositivos de hasta 5 cuentas del mismo navegador.
    """
    ids = ids_de_la_cookie_de_dispositivo(valor)
    return SEPARADOR_DE_DISPOSITIVOS.join(ids) if ids else None


def pon_la_cookie_de_dispositivo(response: Response, device_id: str, request: Request) -> None:
    """La cookie del dispositivo, con este delante y los de otras cuentas detrás (BE #737)."""
    anteriores = ids_de_la_cookie_de_dispositivo(request.cookies.get(get_device_id_cookie_name()))
    set_device_id_cookie(response, valor_de_la_cookie_de_dispositivo(device_id, anteriores))
