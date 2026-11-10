"""El puerto de los correos que salen sin que la petición los espere (fase 3, B1-B2)."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable


class ICorreoEnSegundoPlano(ABC):
    """Quien lanza un envío de correo y vuelve enseguida.

    El registro responde igual exista o no el correo, también en el tiempo: el correo
    de verificación (correo nuevo) y el aviso al dueño (cuenta verificada) salen así, y
    ninguno alarga la respuesta. Un envío que falla no sube: se queda en el log.
    """

    @abstractmethod
    def lanza(self, nombre: str, envio: Callable[[], Awaitable[object]]) -> None:
        """Lanza `envio()` sin esperarlo. `nombre` lo identifica en el log y en los tests."""
