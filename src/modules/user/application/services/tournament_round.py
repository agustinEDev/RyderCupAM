"""
La vuelta propia de un partido de torneo, para el panel y las estadísticas (BE #517).

Las dos pantallas tienen que medirla igual: el índice que guardó el partido (o
el del perfil si falta), con la pendiente y el rating de su barra, al 100 %,
por `personal_playing_handicap`, la misma pieza que mide la partida rápida.
"""

from decimal import Decimal

from src.modules.golf_course.domain.services.stroke_context import StrokeContextBuilder
from src.shared.domain.services.personal_round import personal_playing_handicap


def tournament_index(player, profile_handicap: float | None) -> float | Decimal | None:
    """
    El índice con el que jugó: la foto que guardó el partido al generarse, que es
    lo que el WHS quiere para medir una vuelta antigua; si falta, el del perfil.
    """
    if player is not None and player.player_handicap is not None:
        return player.player_handicap
    return profile_handicap


def is_scratch(competition) -> bool:
    """La misma regla que la partida rápida: scratch es no admitir hándicap."""
    return competition is not None and not competition.play_mode.allows_handicap()


def tournament_personal_handicap(
    course, player, profile_handicap: float | None, *, scratch: bool
) -> int | None:
    """Hándicap de juego de la vuelta propia de un jugador en un partido de torneo."""
    tee_rating = (
        StrokeContextBuilder.build(course).rating_for(player.tee_color, player.tee_gender)
        if course is not None and player is not None
        else None
    )
    return personal_playing_handicap(
        tournament_index(player, profile_handicap), tee_rating, scratch=scratch
    )
