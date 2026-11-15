"""
Correo verificado para lo que llega a otras personas (B-17 de la auditoría de la fase 6).

Una cuenta sin verificar pudo crearla cualquiera con un correo que no es suyo; con ella se
podía crear competiciones, pedir amistad e invitar, y usar eso para molestar o para
averiguar cuentas. Desde el 15 nov 2026 (Agustín) esas tres acciones piden el correo
verificado; entrar, ver, jugar partidas rápidas y ACEPTAR lo que te manden, no. Las
cuentas de Google llegan verificadas.

Como la guarda de los Términos (`terms_guard.py`): una dependencia que sustituye a
`get_current_user` en esas rutas y un error con su código, que responde el mismo
manejador de los Términos (403 con `detail` y `error_code`).
"""

from fastapi import Depends

from src.config.dependencies import get_current_user
from src.modules.user.application.dto.user_dto import UserResponseDTO

EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"
# En los dos idiomas, como el de los Términos: una versión vieja de la app lo pinta tal cual
EMAIL_NOT_VERIFIED_MESSAGE = (
    "Verifica tu correo para invitar, pedir amistad o crear competiciones. / "
    "Verify your email to invite, send friend requests or create competitions."
)


class EmailNotVerifiedError(Exception):
    """El usuario no ha verificado su correo y la acción llega a otras personas."""

    error_code = EMAIL_NOT_VERIFIED

    def __init__(self, message: str = EMAIL_NOT_VERIFIED_MESSAGE):
        super().__init__(message)


async def usuario_con_correo_verificado(
    current_user: UserResponseDTO = Depends(get_current_user),
) -> UserResponseDTO:
    """El usuario actual, si ha verificado su correo."""
    if not current_user.email_verified:
        raise EmailNotVerifiedError()
    return current_user
