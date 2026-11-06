"""El tope global de correos de «intentos fallidos» (BE #732)."""

from abc import ABC, abstractmethod


class ICupoDeAvisos(ABC):
    """Cuántos avisos de fallos caben en esta hora, en toda la app.

    Los provoca un atacante: sin tope, una red bloqueando cuentas gastaría el cupo
    diario del proveedor de correo, que comparten la verificación y la recuperación
    de contraseña.
    """

    @abstractmethod
    def reserva(self, motivo: str) -> bool:
        """Reserva un aviso de este motivo. False si su tope está lleno."""

    @abstractmethod
    def devuelve(self, motivo: str) -> None:
        """Devuelve un aviso reservado que al final no se envió."""
