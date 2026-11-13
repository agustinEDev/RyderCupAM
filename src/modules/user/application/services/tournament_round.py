"""
La vuelta propia de un partido de torneo, para el historial y las estadísticas (BE #517).

El índice que guardó el partido (o el del perfil si falta), con la pendiente y
el rating de su barra, por `personal_playing_handicap`, la misma pieza que mide
la partida rápida. Las estadísticas, al 100 %; el historial, con el allowance de
la modalidad: «Tu vuelta» es la real de la partida (Agustín, 24 oct 2026).
"""

from decimal import Decimal
from typing import Protocol

from src.modules.competition.domain.entities.competition import Competition
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.services.stroke_context import StrokeContextBuilder
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.services.personal_round import (
    PERSONAL_ROUND_ALLOWANCE,
    personal_playing_handicap,
)
from src.shared.domain.value_objects.gender import Gender


class TournamentPlayer(Protocol):
    """Lo que la vuelta propia lee del jugador: el de un partido o el de un grupo."""

    @property
    def player_handicap(self) -> Decimal | None: ...

    @property
    def tee_color(self) -> TeeColor: ...

    @property
    def tee_gender(self) -> Gender | None: ...


def tournament_index(
    player: TournamentPlayer | None, profile_handicap: float | None
) -> float | Decimal | None:
    """
    El índice con el que jugó: la foto que guardó el partido al generarse, que es
    lo que el WHS quiere para medir una vuelta antigua; si falta, el del perfil.
    """
    if player is not None and player.player_handicap is not None:
        return player.player_handicap
    return profile_handicap


def is_scratch(competition: Competition | None) -> bool:
    """La misma regla que la partida rápida: scratch es no admitir hándicap."""
    return competition is not None and not competition.play_mode.allows_handicap()


def tournament_personal_handicap(
    course: GolfCourse | None,
    player: TournamentPlayer | None,
    profile_handicap: float | None,
    *,
    scratch: bool,
    allowance: int = PERSONAL_ROUND_ALLOWANCE,
) -> int | None:
    """Hándicap de juego de la vuelta propia de un jugador en un partido de torneo."""
    tee_rating = (
        StrokeContextBuilder.build(course).rating_for(player.tee_color, player.tee_gender)
        if course is not None and player is not None
        else None
    )
    return personal_playing_handicap(
        tournament_index(player, profile_handicap), tee_rating, scratch=scratch, allowance=allowance
    )
