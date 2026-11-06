"""Demasiados intentos de login desde un origen en un minuto (BE #732)."""


class LoginAttemptsExceededException(Exception):  # noqa: N818 - como las demás del módulo
    """El origen (red o dispositivo fiable) agotó los intentos de este minuto para
    este correo, o la red agotó su techo de fallos (`techo_de_red`). La ruta lo
    responde con el mismo 429 que el rate limit."""

    def __init__(self, techo_de_red: bool = False):
        self.techo_de_red = techo_de_red
        super().__init__("Too many login attempts")
