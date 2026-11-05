"""
La cookie del dispositivo: los de hasta 5 cuentas del mismo navegador (BE #737).

Una sola pieza para leerla y escribirla: el login, el de Google, el refresco y el
registro de dispositivos la leen igual. La controla el cliente: lo que no sea un
UUID se descarta, y nunca más de MAXIMO_DE_DISPOSITIVOS_EN_LA_COOKIE.
"""

import uuid

SEPARADOR_DE_DISPOSITIVOS = "."
MAXIMO_DE_DISPOSITIVOS_EN_LA_COOKIE = 5


def ids_de_la_cookie_de_dispositivo(valor: str | None) -> list[str]:
    """Los ids válidos de la cookie, normalizados, en orden y sin repetir."""
    ids: list[str] = []
    for parte in (valor or "").split(SEPARADOR_DE_DISPOSITIVOS)[
        : MAXIMO_DE_DISPOSITIVOS_EN_LA_COOKIE * 2
    ]:
        try:
            normalizado = str(uuid.UUID(parte.strip()))
        except (ValueError, AttributeError):
            continue
        if normalizado not in ids:
            ids.append(normalizado)
    return ids[:MAXIMO_DE_DISPOSITIVOS_EN_LA_COOKIE]


def valor_de_la_cookie_de_dispositivo(device_id: str, anteriores: list[str] | None = None) -> str:
    """El valor de la cookie: este dispositivo delante y los demás de antes detrás."""
    resto = [d for d in (anteriores or []) if d != device_id]
    return SEPARADOR_DE_DISPOSITIVOS.join([device_id, *resto][:MAXIMO_DE_DISPOSITIVOS_EN_LA_COOKIE])
