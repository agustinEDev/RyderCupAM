"""Puerto: las partidas que han jugado juntos dos jugadores."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from src.modules.social.domain.services.head_to_head import Outcome, Relation
from src.modules.user.domain.value_objects.user_id import UserId


class SharedGameKind(StrEnum):
    """De donde sale la partida, que es a donde lleva tocarla."""

    QUICK_MATCH = "QUICK_MATCH"
    TOURNAMENT_MATCH = "TOURNAMENT_MATCH"
    TOURNAMENT_GROUP = "TOURNAMENT_GROUP"
    # Un torneo stroke play COMPLETADO, entero: una sola entrada por torneo,
    # con los dos puestos de la general final (tabla del 22 oct 2026, J)
    TOURNAMENT_STROKE_PLAY = "TOURNAMENT_STROKE_PLAY"


@dataclass(frozen=True)
class StrokePlayStanding:
    """
    Los dos puestos en la general final de un stroke play (J): «4.º y 7.º de
    16». Sin puesto (None) quien no quedo clasificado (retirado, NR).
    """

    my_position: int | None
    my_tied: bool
    their_position: int | None
    their_tied: bool
    total_players: int


@dataclass(frozen=True)
class SharedGame:
    """
    Una partida terminada que jugaron los dos, vista desde quien mira.

    `outcome` es None cuando no cuenta para el cara a cara (sin resultado, o
    una tarjeta a medias), aunque si salga en «Partidas juntos».

    `unfinished` marca la partida rapida que no cuenta para alguno de los dos
    por los hoyos que anoto (tabla del 22 oct 2026, A): sale «sin terminar» y
    su `outcome` es None.
    `game_id` es el id de la partida rapida, del partido o del grupo.

    `played_at` es el instante en que se jugo, en UTC y sin zona: ordena las
    del mismo dia. None si no se sabe; entonces cuenta como el principio del
    dia.
    """

    kind: SharedGameKind
    game_id: str
    played_on: date
    golf_course_id: str | None
    golf_course_name: str | None
    format: str
    relation: Relation
    outcome: Outcome | None
    competition_id: str | None = None
    competition_name: str | None = None
    played_at: datetime | None = None
    unfinished: bool = False
    # Solo en TOURNAMENT_STROKE_PLAY
    standing: StrokePlayStanding | None = None


class SharedGamesInterface(ABC):
    """
    Junta las partidas rapidas y las de torneo que dos jugadores terminaron
    juntos.

    Es un puerto porque la respuesta cruza tres modulos (partida rapida,
    competicion y campos): `social` no lee sus tablas, pregunta aqui.
    """

    @abstractmethod
    async def between(self, viewer_id: UserId, other_id: UserId) -> list[SharedGame]:
        """
        Las terminadas que jugaron los dos, en cualquier orden.

        Fuera las partidas rapidas que cualquiera de los dos oculto, las que
        no acabaron y los partidos sin jugar (walkover).
        """
