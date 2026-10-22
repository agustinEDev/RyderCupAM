"""Puerto: la primera vuelta de un jugador en un campo."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from src.modules.social.application.exclusive_achievements import PlayedKey, played_key
from src.modules.user.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class CourseRound:
    """
    Una vuelta del jugador en un campo, reducida a cuando se jugo y de donde sale.

    - `instant`: en UTC y sin zona. Una ronda de torneo, la hora a la que abre
      su sesion en la zona del campo (`round_instant`); una partida rapida, su
      creacion.
    - `source_id`: el partido de la Ryder, el grupo de stroke play o la partida
      rapida.
    - `competition_id`: el torneo, o None si es una partida rapida.
    """

    instant: datetime
    source_id: str
    competition_id: str | None = None

    @property
    def key(self) -> PlayedKey:
        """La misma clave con la que se comparan los logros publicados (`event_key`)."""
        return played_key(self.instant, self.competition_id, self.source_id)


class PlayerCourseHistoryInterface(ABC):
    """
    Responde cual fue la primera vuelta de un jugador en un campo, mirando
    **todo** lo que ha jugado.

    Es un puerto y no una consulta directa porque la respuesta cruza dos
    modulos: un campo se puede estrenar en una partida rapida o en un torneo, y
    preguntarle solo a uno haria que el mismo campo se estrenara dos veces.
    """

    @abstractmethod
    async def first_round_on_course(
        self, user_id: UserId, golf_course_id: str, timezone: str | None
    ) -> CourseRound | None:
        """
        La vuelta mas antigua del jugador en ese campo (por `CourseRound.key`),
        o None si no tiene ninguna. Una vuelta estrena el campo si es esta.

        Cuentan las partidas rapidas terminadas y las vueltas de torneos
        CERRADOS, salvo NO_PRESENTADO (quien se retiro si piso el campo): un
        torneo en juego todavia no ha publicado nada, y uno cancelado nunca lo
        hara (decision del 22 oct 2026).

        `timezone` es la del campo: con ella se situa cada ronda de torneo en
        el.
        """
