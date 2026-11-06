"""Demasiados intentos de login desde un origen en un minuto (BE #732)."""


class LoginAttemptsExceededException(Exception):  # noqa: N818 - como las demás del módulo
    """El origen (red o dispositivo fiable) agotó los intentos de este minuto para
    este correo. La ruta lo responde con el mismo 429 que el rate limit."""
