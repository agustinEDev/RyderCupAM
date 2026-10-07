"""
RefrescoDeHandicapsService - Quién se refresca con la RFEG en un día de juego (BE #502).

Decidido con Agustín el 7 oct 2026. La RFEG publica hacia las 0:00-0:30, y un
jugador puede haber jugado otro torneo la víspera: a las **3:00 hora del campo
de cada día de juego** se pregunta por el hándicap de quien juega ese día.

- **Nunca a quien ya ha empezado hoy** su partido o su partida: su hándicap de
  hoy ya está fijado. Lo jugado no se toca.
- **Ni a quien tiene hándicap personalizado**: ese lo puso el organizador.
- Si el servidor estuvo caído a las 3:00, el primer intento se hace en cuanto
  vuelve, aunque sea tarde.
- Lo que la RFEG **no encuentra** no se reintenta; lo que **falla** (no
  responde) se reintenta en cada vuelta **hasta las 7:00**, antes de que se
  empiece a jugar.

Aquí solo está la decisión, sin red ni base de datos.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum

from src.modules.user.domain.value_objects.user_id import UserId

HORA_DEL_REFRESCO = time(3, 0)
FIN_DE_LOS_REINTENTOS = time(7, 0)


class ResultadoRefresco(StrEnum):
    """Qué pasó al preguntar a la RFEG por un jugador, un día de juego."""

    ACTUALIZADO = "ACTUALIZADO"
    NO_ENCONTRADO = "NO_ENCONTRADO"
    SIN_LICENCIA_ESPANOLA = "SIN_LICENCIA_ESPANOLA"
    FALLIDO = "FALLIDO"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Candidato:
    """Un jugador que juega ese día, con lo que decide si se le pregunta."""

    user_id: UserId
    handicap_personalizado: bool
    empezo_hoy: bool


class RefrescoDeHandicapsService:
    """Cuándo toca refrescar y a quién."""

    @staticmethod
    def toca(ahora_local: datetime, dia_de_juego: date) -> bool:
        """
        Si ya toca refrescar para ese día de juego.

        Args:
            ahora_local: La hora actual en el huso del campo
            dia_de_juego: El día en que se juega
        """
        return ahora_local.date() == dia_de_juego and ahora_local.time() >= HORA_DEL_REFRESCO

    @staticmethod
    def a_quien(
        candidatos: Iterable[Candidato],
        resultados: Mapping[UserId, ResultadoRefresco],
        ahora_local: datetime,
    ) -> list[UserId]:
        """
        A quién preguntar en esta vuelta, en el orden de los candidatos.

        Args:
            candidatos: Quien juega ese día
            resultados: Lo que ya se le preguntó ese día a cada uno
            ahora_local: La hora actual en el huso del campo
        """
        reintenta = ahora_local.time() < FIN_DE_LOS_REINTENTOS
        elegidos = []
        for candidato in candidatos:
            if candidato.empezo_hoy or candidato.handicap_personalizado:
                continue
            resultado = resultados.get(candidato.user_id)
            if resultado is None or (resultado is ResultadoRefresco.FALLIDO and reintenta):
                elegidos.append(candidato.user_id)
        return elegidos
