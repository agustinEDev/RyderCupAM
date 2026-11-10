"""El puerto del reenvío del enlace de verificación en segundo plano (fase 3, revisión)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.modules.user.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class ReenvioDeVerificacion:
    """Lo que hace falta para enviar un enlace nuevo y guardarlo después."""

    user_id: UserId
    to_email: str
    user_name: str
    token: str


class IReenvioDeVerificacion(ABC):
    """Quien envía el enlace nuevo y, si salió, lo guarda; sin que la petición espere.

    Si el envío falla no se guarda nada: el enlace de antes sigue valiendo. Nunca lanza.
    """

    @abstractmethod
    def lanza(self, datos: ReenvioDeVerificacion) -> None:
        """Lanza el envío (y el guardado) y vuelve enseguida."""
