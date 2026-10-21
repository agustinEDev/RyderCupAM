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

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType

from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus

# Lo que tarda la pasada por jugador, de sobra: el margen antes de cada salida
SEGUNDOS_POR_JUGADOR = 10
# El vigilante pasa cada minuto y la vuelta tarda: lo programado tiene que caber
# con este margen dentro de la ventana
MARGEN_AL_PROGRAMAR = timedelta(minutes=2)


@dataclass(frozen=True)
class Jornada:
    """Un día de juego: su primera salida y cuándo acaba (medianoche del campo)."""

    primera_salida: datetime
    fin: datetime


class CodigoDeVentana(StrEnum):
    """Por qué no se puede actualizar, como código para el idioma de la app (#541)."""

    STATUS = "STATUS"
    NO_WINDOWS = "NO_WINDOWS"
    RYDER = "RYDER"
    DAY_IN_PLAY = "DAY_IN_PLAY"
    NO_DAYS_LEFT = "NO_DAYS_LEFT"
    TOO_CLOSE = "TOO_CLOSE"
    NO_TIMEZONE = "NO_TIMEZONE"
    DISABLED = "DISABLED"
    RUNNING = "RUNNING"
    # Solo al programarla
    IN_THE_PAST = "IN_THE_PAST"
    TOO_TIGHT = "TOO_TIGHT"


# El texto de cada motivo, uno solo: lo dicen el dominio, los casos de uso y la
# ruta, que no copia nada (BE #562). RUNNING, exacto: lo simula un test del frontend
MOTIVOS_DE_LA_VENTANA: Mapping[CodigoDeVentana, str] = MappingProxyType(
    {
        CodigoDeVentana.STATUS: (
            "Los hándicaps se actualizan desde que se cierran las inscripciones hasta que "
            "termina la competición."
        ),
        CodigoDeVentana.NO_WINDOWS: "Sin franjas, se actualizan hasta iniciar la competición.",
        CodigoDeVentana.RYDER: "En una Ryder se actualizan hasta iniciar la competición.",
        CodigoDeVentana.DAY_IN_PLAY: "Hay una jornada en marcha: se podrá al acabar el día.",
        CodigoDeVentana.NO_DAYS_LEFT: "Ya no quedan jornadas por jugar.",
        CodigoDeVentana.TOO_CLOSE: (
            "Queda muy poco para la siguiente salida: no daría tiempo a preguntar por todos."
        ),
        CodigoDeVentana.NO_TIMEZONE: "El campo de la franja no tiene zona horaria.",
    }
)
# Los que no salen de la ventana: al programar van sin prefijo
MOTIVOS_SIN_VENTANA: Mapping[CodigoDeVentana, str] = MappingProxyType(
    {
        CodigoDeVentana.IN_THE_PAST: "Prográmala para un momento en el futuro.",
        CodigoDeVentana.TOO_TIGHT: (
            "Demasiado justo: prográmala con al menos "
            f"{int(MARGEN_AL_PROGRAMAR.total_seconds() // 60)} minutos de margen antes de "
            "que se cierre la ventana."
        ),
        CodigoDeVentana.DISABLED: "La actualización con la RFEG solo está encendida en producción.",
        CodigoDeVentana.RUNNING: "Ya se están actualizando los hándicaps.",
    }
)
MOTIVOS: Mapping[CodigoDeVentana, str] = MappingProxyType(
    {**MOTIVOS_DE_LA_VENTANA, **MOTIVOS_SIN_VENTANA}
)
# Al programar, el motivo de la ventana se mira a la hora pedida
PREFIJO_A_ESA_HORA = "A esa hora no se podría: "


@dataclass(frozen=True)
class Ventana:
    """Si se puede actualizar ahora, hasta cuándo, y si no, por qué."""

    abierta: bool
    cierra: datetime | None = None
    motivo: str | None = None
    # El motivo como código, para que el cliente lo diga en su idioma (#541)
    codigo: CodigoDeVentana | None = None


class VentanaDeActualizacion:
    """Calcula la ventana del botón de actualizar hándicaps."""

    MOTIVO_ESTADO = MOTIVOS[CodigoDeVentana.STATUS]

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
                False, motivo=VentanaDeActualizacion.MOTIVO_ESTADO, codigo=CodigoDeVentana.STATUS
            )
        if not stroke_play or not jornadas:
            if status is CompetitionStatus.CLOSED:
                return Ventana(True)
            if stroke_play:
                return Ventana(
                    False,
                    motivo=MOTIVOS[CodigoDeVentana.NO_WINDOWS],
                    codigo=CodigoDeVentana.NO_WINDOWS,
                )
            return Ventana(
                False,
                motivo=MOTIVOS[CodigoDeVentana.RYDER],
                codigo=CodigoDeVentana.RYDER,
            )
        return VentanaDeActualizacion._entre_jornadas(jornadas, jugadores, ahora)

    @staticmethod
    def _entre_jornadas(jornadas: list[Jornada], jugadores: int, ahora: datetime) -> Ventana:
        """Un stroke play con franjas: entre jornadas y con margen antes de la siguiente."""
        for jornada in jornadas:
            if jornada.primera_salida <= ahora < jornada.fin:
                return Ventana(
                    False,
                    motivo=MOTIVOS[CodigoDeVentana.DAY_IN_PLAY],
                    codigo=CodigoDeVentana.DAY_IN_PLAY,
                )
        siguientes = [j.primera_salida for j in jornadas if j.primera_salida > ahora]
        if not siguientes:
            return Ventana(
                False,
                motivo=MOTIVOS[CodigoDeVentana.NO_DAYS_LEFT],
                codigo=CodigoDeVentana.NO_DAYS_LEFT,
            )
        cierra = min(siguientes) - timedelta(seconds=SEGUNDOS_POR_JUGADOR * jugadores)
        if ahora >= cierra:
            return Ventana(
                False,
                cierra=cierra,
                motivo=MOTIVOS[CodigoDeVentana.TOO_CLOSE],
                codigo=CodigoDeVentana.TOO_CLOSE,
            )
        return Ventana(True, cierra=cierra)
