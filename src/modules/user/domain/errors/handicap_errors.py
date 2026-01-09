"""
Handicap Domain Errors - Domain Layer

Define las excepciones relacionadas con el servicio de hándicap.
"""


class HandicapServiceError(Exception):
    """
    Error base para problemas con el servicio de hándicap.

    Todos los errores específicos de hándicap heredan de esta clase.
    """

    pass


class HandicapNotFoundError(HandicapServiceError):
    """
    El hándicap no fue encontrado para el jugador especificado.

    Se lanza cuando la búsqueda no devuelve resultados.
    """

    pass


class HandicapServiceUnavailableError(HandicapServiceError):
    """
    El servicio de hándicap no está disponible.

    Se lanza cuando hay problemas de conectividad o el servicio externo
    no responde correctamente.
    """

    pass
