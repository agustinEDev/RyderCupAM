"""
VentanaDeActualizacion - Cuándo se pueden actualizar los hándicaps a mano (#251).

Decidido con Agustín el 7 oct 2026. El organizador puede pedir a la RFEG los
hándicaps de sus jugadores con un botón (o dejarlo programado):

- **Desde que se cierran las inscripciones.**
- **Hasta 10 s por jugador antes de la siguiente salida**: lo que tarda la
  pasada, para que acabe antes de que salga nadie.
- **Nunca con una jornada en marcha**: de su primera salida a medianoche,
  hora del campo.
- **En una Ryder**, que no tiene horas de salida, del cierre a iniciar.

Aquí solo está la decisión: las jornadas llegan ya en horas absolutas.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus

# Lo que tarda la pasada por jugador, de sobra: el margen antes de cada salida
SEGUNDOS_POR_JUGADOR = 10


@dataclass(frozen=True)
class Jornada:
    """Un día de juego: su primera salida y cuándo acaba (medianoche del campo)."""

    primera_salida: datetime
    fin: datetime


@dataclass(frozen=True)
class Ventana:
    """Si se puede actualizar ahora, hasta cuándo, y si no, por qué."""

    abierta: bool
    cierra: datetime | None = None
    motivo: str | None = None


class VentanaDeActualizacion:
    """Calcula la ventana del botón de actualizar hándicaps."""

    @staticmethod
    def calcular(
        stroke_play: bool,
        status: CompetitionStatus,
        jornadas: list[Jornada],
        jugadores: int,
        ahora: datetime,
    ) -> Ventana:
        """
        Args:
            stroke_play: Si es un Stableford o un Medal
            status: El estado de la competición
            jornadas: Sus días de juego, en horas absolutas (vacío en una Ryder)
            jugadores: Cuántos inscritos hay que preguntar (para el margen)
            ahora: La hora actual, con huso
        """
        if status not in (CompetitionStatus.CLOSED, CompetitionStatus.IN_PROGRESS):
            return Ventana(
                False,
                motivo="Los hándicaps se actualizan desde que se cierran las inscripciones "
                "hasta que termina la competición.",
            )
        if not stroke_play or not jornadas:
            if status is CompetitionStatus.CLOSED:
                return Ventana(True)
            return Ventana(False, motivo="En una Ryder se actualizan hasta iniciar la competición.")
        return VentanaDeActualizacion._entre_jornadas(jornadas, jugadores, ahora)

    @staticmethod
    def _entre_jornadas(jornadas: list[Jornada], jugadores: int, ahora: datetime) -> Ventana:
        """Un stroke play con franjas: entre jornadas y con margen antes de la siguiente."""
        for jornada in jornadas:
            if jornada.primera_salida <= ahora < jornada.fin:
                return Ventana(
                    False, motivo="Hay una jornada en marcha: se podrá al acabar el día."
                )
        siguientes = [j.primera_salida for j in jornadas if j.primera_salida > ahora]
        if not siguientes:
            return Ventana(False, motivo="Ya no quedan jornadas por jugar.")
        cierra = min(siguientes) - timedelta(seconds=SEGUNDOS_POR_JUGADOR * jugadores)
        if ahora >= cierra:
            return Ventana(
                False,
                cierra=cierra,
                motivo="Queda muy poco para la siguiente salida: no daría tiempo a "
                "preguntar por todos.",
            )
        return Ventana(True, cierra=cierra)
