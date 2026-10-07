"""
ActualizacionDeHandicaps - Una actualización de hándicaps con la RFEG (#251).

Decidido con Agustín el 7 oct 2026. Al cerrar las inscripciones se pregunta a
la RFEG por el hándicap de cada inscrito (en la PR siguiente, también con el
botón del organizador o a una hora programada). Cada vez es una actualización,
con el resultado de cada jugador apuntado aparte.

Si termina con alguien pendiente queda incompleta, y se avisa al organizador.
Al iniciar la competición, o al cerrar de nuevo las inscripciones, la que
estuviera a medias se corta: lo que no se actualizó antes se queda como estaba.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from ..value_objects.competition_id import CompetitionId


class OrigenActualizacion(StrEnum):
    """Qué la lanzó."""

    CIERRE = "ENROLLMENTS_CLOSED"
    BOTON = "ORGANIZER"
    PROGRAMADA = "SCHEDULED"


class EstadoActualizacion(StrEnum):
    """Cómo va."""

    EN_CURSO = "IN_PROGRESS"
    COMPLETA = "COMPLETED"
    INCOMPLETA = "INCOMPLETE"
    CORTADA = "STOPPED"


@dataclass
class ActualizacionDeHandicaps:
    """Una actualización de los hándicaps de una competición."""

    id: uuid.UUID
    competition_id: CompetitionId
    origen: OrigenActualizacion
    creada: datetime
    estado: EstadoActualizacion = EstadoActualizacion.EN_CURSO
    terminada: datetime | None = field(default=None)

    @classmethod
    def crear(
        cls, competition_id: CompetitionId, origen: OrigenActualizacion, momento: datetime
    ) -> "ActualizacionDeHandicaps":
        """Una actualización nueva, en curso."""
        return cls(id=uuid.uuid4(), competition_id=competition_id, origen=origen, creada=momento)

    def sigue(self) -> bool:
        """Si todavía hay que preguntar por alguien en esta pasada."""
        return self.estado is EstadoActualizacion.EN_CURSO

    def terminar(self, pendientes: int, momento: datetime) -> None:
        """
        Acaba la pasada: completa, o incompleta si alguien se quedó sin actualizar.

        Si ya estaba cortada (la competición empezó a mitad), sigue cortada.
        """
        if not self.sigue():
            return
        self.estado = EstadoActualizacion.INCOMPLETA if pendientes else EstadoActualizacion.COMPLETA
        self.terminada = momento

    def cortar(self, momento: datetime) -> None:
        """
        La competición empezó o se cerró de nuevo: lo pendiente ya no se actualiza.

        Una completa sigue completa.
        """
        if self.estado in (EstadoActualizacion.EN_CURSO, EstadoActualizacion.INCOMPLETA):
            self.estado = EstadoActualizacion.CORTADA
            self.terminada = momento
