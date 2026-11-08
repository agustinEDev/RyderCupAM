"""
El 429 de los cambios de seguridad (BE #753): un código y un texto, el mismo en
PATCH /users/security y en POST /auth/reauthenticate, que comparten el contador.
"""

from fastapi import status
from fastapi.responses import JSONResponse

from src.config.rate_limit import SECURITY_CHANGES_LIMIT, cabe, clave_de_usuario
from src.shared.infrastructure.api.respuesta_con_codigo import respuesta_con_codigo

DEMASIADOS_CAMBIOS = "TOO_MANY_SECURITY_CHANGES"
DEMASIADOS_CORREOS_NUEVOS = "TOO_MANY_EMAIL_CHANGE_REQUESTS"
# Sin el límite ni la ventana: no es asunto de quien llama
TEXTOS = {
    DEMASIADOS_CAMBIOS: "Demasiados intentos. Inténtalo de nuevo más tarde.",
    DEMASIADOS_CORREOS_NUEVOS: "Has pedido demasiados cambios de correo. Inténtalo más tarde.",
}


def cabe_otro_cambio(user_id: str) -> bool:
    """Cuenta una petición contra el límite de seguridad del usuario."""
    return cabe(SECURITY_CHANGES_LIMIT, "security-changes", clave_de_usuario(user_id))


def demasiados(codigo: str) -> JSONResponse:
    """El 429 con su código, para que el front lo traduzca."""
    return respuesta_con_codigo(status.HTTP_429_TOO_MANY_REQUESTS, TEXTOS, codigo)
