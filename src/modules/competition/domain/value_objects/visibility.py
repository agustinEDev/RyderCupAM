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

    def shows_real_name(self, chosen: bool) -> bool:
        """
        Si el nombre real de un jugador va a la vista en esta competición (SB-08).

        En una pública, siempre: es lo que piden actas, premios y la RFEG, y quien
        tenga alias lo lleva además, debajo. En una privada, lo que eligió el jugador
        al apuntarse (`chosen`, su `use_real_name`). Decidido por Agustín el 17 nov 2026.
        """
        return self == Visibility.PUBLIC or chosen

    def __str__(self) -> str:
        return self.value
