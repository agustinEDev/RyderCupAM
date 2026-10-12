"""
RefrescoDeHandicapsService - A quién se pregunta a la RFEG en una actualización (#251).

Decidido con Agustín el 7 oct 2026: al cerrar las inscripciones se pregunta a
la RFEG por el hándicap de cada inscrito, como hace la federación con su base
de datos al cierre. Sustituye al refresco de las 3:00 de cada día de juego (BE #502).

- **Nunca a quien tiene hándicap personalizado**: ese lo puso el organizador.
- Lo que la RFEG ya contestó (actualizado, no encontrado, sin licencia
  española) no se repite: si una actualización quedó a medias, la siguiente
  pasada termina solo lo que falta.
- Lo que **falló** se vuelve a preguntar. Cada pasada hace hasta
  `MAX_INTENTOS` por jugador.

Aquí solo está la decisión, sin red ni base de datos.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from src.modules.user.domain.value_objects.user_id import UserId

# Intentos por jugador en cada pasada
MAX_INTENTOS = 3


class ResultadoRefresco(StrEnum):
    """Qué pasó al preguntar a la RFEG por un jugador."""

    ACTUALIZADO = "ACTUALIZADO"
    NO_ENCONTRADO = "NO_ENCONTRADO"
    SIN_LICENCIA_ESPANOLA = "SIN_LICENCIA_ESPANOLA"
    FALLIDO = "FALLIDO"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Candidato:
    """Un inscrito, con lo que decide si se le pregunta."""

    user_id: UserId
    handicap_personalizado: bool


@dataclass(frozen=True)
class Intento:
    """El último resultado de un jugador en una actualización, y cuántas veces se preguntó."""

    resultado: ResultadoRefresco
    intentos: int


class RefrescoDeHandicapsService:
    """A quién preguntar en esta vuelta."""

    @staticmethod
    def a_quien(
        candidatos: Iterable[Candidato], resultados: Mapping[UserId, ResultadoRefresco]
    ) -> list[UserId]:
        """
        A quién preguntar, en el orden de los candidatos.

        Args:
            candidatos: Los inscritos de la competición
            resultados: Lo que ya contestó la RFEG por cada uno en esta actualización
        """
        return [
            c.user_id
            for c in candidatos
            if not c.handicap_personalizado
            and resultados.get(c.user_id, ResultadoRefresco.FALLIDO) is ResultadoRefresco.FALLIDO
        ]
