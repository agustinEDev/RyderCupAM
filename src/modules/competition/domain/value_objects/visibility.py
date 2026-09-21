"""
Visibility Value Object - Quien ve una competicion y quien puede pedir sitio.

Una **privada** es invisible para quien no esta dentro: se entra porque el
organizador invita. Es la Ryder entre amigos, que es lo que hay hoy.

Una **publica** se ve y cualquiera puede pedir plaza — que el organizador
seguira aprobando o rechazando. Es el campeonato de un club.

Es un enum y no un booleano porque los clubes vienen detras (FE #652): un
tercer caso, «solo para quien sigue al club», no deberia obligar a cambiar el
tipo de la columna.
"""

from enum import StrEnum


class Visibility(StrEnum):
    """Quien puede ver una competicion y pedir sitio en ella."""

    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"

    def is_discoverable(self) -> bool:
        """Indica si sale en la pantalla de explorar para quien no esta dentro."""
        return self == Visibility.PUBLIC

    def accepts_enrollment_requests(self) -> bool:
        """Indica si un desconocido puede pedir plaza por su cuenta."""
        return self == Visibility.PUBLIC

    def __str__(self) -> str:
        return self.value
