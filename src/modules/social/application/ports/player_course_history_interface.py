"""Puerto: si un jugador ya habia pisado un campo."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

from src.modules.user.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class PlayedBefore:
    """
    El momento de la vuelta que se juzga: solo cuenta lo jugado ANTES de el
    (prueba de punta a punta, 22 oct 2026: el mismo dia, por hora real).

    - `day`: el dia local de la ronda.
    - `local_hour`: la hora local a la que abre su sesion (6, 12 o 18). Basta
      para ordenarla frente a otra ronda del MISMO campo, que tiene su misma
      zona, aunque la zona no se sepa.
    - `utc_instant`: ese mismo momento en UTC y sin zona, si el campo tiene
      zona. Es con lo que se compara el instante de creacion de una partida
      rapida.

    Lo que no se sepa se compara por fecha, de forma conservadora: el mismo dia
    no cuenta como «antes».
    """

    day: date
    local_hour: int | None = None
    utc_instant: datetime | None = None


class PlayerCourseHistoryInterface(ABC):
    """
    Responde si una vuelta estrena campo, mirando **todo** lo que el jugador ha
    jugado.

    Es un puerto y no una consulta directa porque la respuesta cruza dos
    modulos: un campo se puede estrenar en una partida rapida o en un torneo, y
    preguntarle solo a uno haria que el mismo campo se estrenara dos veces.
    """

    @abstractmethod
    async def has_played_course_before(
        self,
        user_id: UserId,
        golf_course_id: str,
        excluding_match_id: str,
        excluding_competition_id: str | None = None,
        before: PlayedBefore | None = None,
    ) -> bool:
        """
        Si el jugador ya habia terminado otra vuelta en ese campo.

        `excluding_match_id` deja fuera la vuelta que se esta juzgando: cuando
        esto corre ya esta cerrada, asi que contarla haria que nadie estrenara
        campo nunca.

        `excluding_competition_id` deja fuera el torneo entero que se juzga
        (decision del 22 oct 2026): «campo nuevo» es no haberlo jugado ANTES de
        ese torneo, asi que sus otras vueltas en el campo no lo bloquean. De
        los demas torneos solo cuentan los ya cerrados.

        `before` corta en el tiempo (revision final del 22 oct 2026, afinada el
        mismo dia por hora real): solo cuenta lo jugado ANTES de ese momento
        —la sesion de la otra ronda del campo, o el instante en que se creo la
        partida rapida—, nunca a la vez ni despues. Asi un torneo reabierto y
        vuelto a cerrar no pierde su «campo nuevo» por lo que se jugo luego.
        Ver `PlayedBefore` para lo que se compara cuando falta la zona.
        """
