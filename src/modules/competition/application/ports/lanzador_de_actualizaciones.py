"""
Puerto: lanzar una actualización de hándicaps en segundo plano (#251).

Al cerrar las inscripciones la respuesta no espera a la RFEG: la actualización
se guarda y se lanza aparte. Quien la lance decide cómo (en la API, una tarea
del propio proceso).
"""

import uuid
from abc import ABC, abstractmethod


class LanzadorDeActualizaciones(ABC):
    """Lanza la pasada de una actualización ya guardada, sin esperarla."""

    @abstractmethod
    def lanzar(self, update_id: uuid.UUID) -> None:
        """Se llama con la actualización ya guardada (fuera de la transacción)."""
