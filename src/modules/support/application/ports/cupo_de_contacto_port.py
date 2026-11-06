"""El tope diario del formulario de contacto, en toda la app (6 nov 2026)."""

from abc import ABC, abstractmethod


class ICupoDeContacto(ABC):
    """Cuántos mensajes de contacto caben hoy.

    El cupo diario del proveedor de correo (100) lo comparten la verificación y la
    recuperación de contraseña: el formulario, que es público, no puede gastarlo.
    """

    @abstractmethod
    def reserva(self) -> bool:
        """Reserva un mensaje. False si el tope de hoy está lleno."""

    @abstractmethod
    def devuelve(self) -> None:
        """Devuelve un mensaje reservado que al final no salió."""
