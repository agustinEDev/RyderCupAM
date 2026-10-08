"""El token de reseteo de contraseña no existe, caducó o ya se usó (BE #519)."""


class InvalidResetTokenError(ValueError):
    """
    Token de reseteo inválido o expirado.

    Es un `ValueError` para que el reset lo siga tratando como hasta ahora, y
    lleva su código porque el cliente no puede reconocerlo por el texto: va en
    español («inválido»), y la pantalla buscaba «invalid» y nunca lo encontraba.
    """

    code = "RESET_TOKEN_INVALID"

    def __init__(self, message: str = "Token de reseteo inválido o expirado"):
        super().__init__(message)
