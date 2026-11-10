"""El enlace de verificación del correo caducó (fase 3, C1: vale 48 horas)."""


class VerificationTokenExpiredError(ValueError):
    """
    El enlace de verificación es el de la cuenta, pero pasaron sus 48 horas.

    Es un `ValueError`, como los demás fallos del enlace, y lleva su código para que la
    pantalla diga «enlace caducado» y ofrezca reenviarlo (`POST /auth/resend-verification`).
    Un enlace que no es, o el guardado en claro antes del cambio, no llega aquí: es un
    enlace no válido, sin este código.
    """

    error_code = "VERIFICATION_TOKEN_EXPIRED"
    # El texto que dice también la ruta (BE #562)
    MENSAJE = "El enlace de verificación ha caducado. Pide uno nuevo."

    def __init__(self, message: str = MENSAJE):
        super().__init__(message)
