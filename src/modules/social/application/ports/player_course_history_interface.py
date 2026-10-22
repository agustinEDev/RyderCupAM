"""Puerto: si un jugador ya habia pisado un campo."""

from abc import ABC, abstractmethod
from datetime import date

from src.modules.user.domain.value_objects.user_id import UserId


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
        before: date | None = None,
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

        `before` corta por fecha (revision final del 22 oct 2026): solo cuenta
        lo jugado ANTES de ese dia —la ronda, o el dia en que se creo la
        partida rapida—, nunca el mismo dia ni despues. Asi un torneo reabierto
        y vuelto a cerrar no pierde su «campo nuevo» por lo que se jugo luego.
        """
