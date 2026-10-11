"""EstadoDeTarjeta Value Object - En qué punto está la tarjeta de un jugador en su partida (#251)."""

from enum import StrEnum


class EstadoDeTarjeta(StrEnum):
    """
    - JUGANDO: Se está anotando (o aún no ha empezado)
    - ENTREGADA: El jugador (o el organizador) la entregó (P3)
    - RETIRADO: Lo dejó a medias: NR en Medal; en Stableford cuenta lo jugado (P6)
    - NO_PRESENTADO: No se presentó: sin puesto (P6)
    """

    JUGANDO = "JUGANDO"
    ENTREGADA = "ENTREGADA"
    RETIRADO = "RETIRADO"
    NO_PRESENTADO = "NO_PRESENTADO"

    def __str__(self) -> str:
        return self.value

    def fuera_de_la_partida(self) -> bool:
        """Se retiró o no vino: ni marca ni le marcan (QA del 11 oct 2026)."""
        return self in (EstadoDeTarjeta.RETIRADO, EstadoDeTarjeta.NO_PRESENTADO)
