"""DTOs de estadísticas de jugador (BE #128)."""

# El DTO expone un campo llamado `date`, que sombrearia al tipo dentro de la
# clase: de ahi el alias
from datetime import date as date_type

from pydantic import BaseModel, Field


class PlayerStatsResponseDTO(BaseModel):
    """
    Resumen de rendimiento de un jugador, para el panel.

    `scoring_avg` es la media de golpes netos respecto al par de lo jugado, no
    de golpes brutos: comparar brutos entre campos y hándicaps distintos no
    dice nada. Va en None cuando no hay ninguna ronda terminada, que no es lo
    mismo que una media de cero.
    """

    handicap: float | None = None
    handicap_trend: float | None = Field(
        default=None,
        description=(
            "Siempre None por ahora: no existe histórico de hándicap, solo la "
            "fecha del último cambio. Calcularlo exige tabla nueva (BE #128)."
        ),
    )
    scoring_avg: float | None = None
    rounds_played: int = 0
    tournaments_total: int = 0
    tournaments_active: int = 0


class RecentMatchDTO(BaseModel):
    """
    Una entrada del historial de partidas.

    Unifica partidas rápidas y partidos de torneo, que son cosas distintas: de
    ahí que casi todo sea opcional. `match_format` y `scoring_format` se
    exponen por separado en lugar de fundirse en un único campo `format`,
    porque en el dominio son ejes distintos y mutuamente excluyentes.
    """

    id: str
    date: date_type | None = None
    match_format: str | None = None
    scoring_format: str | None = None
    golf_course_id: str | None = None
    golf_course_name: str | None = None
    tournament_name: str | None = None
    result: str | None = Field(
        default=None, description="WON / LOST / HALVED en match play; None si no aplica"
    )
    score: str | None = Field(
        default=None, description='Neto respecto al par ("PAR", "+4") o puntos Stableford'
    )
    stableford_points: int | None = None
    partners: list[str] = Field(default_factory=list)
    opponents: list[str] = Field(default_factory=list)


class RecentMatchesResponseDTO(BaseModel):
    """Historial de partidas del jugador, de la más reciente a la más antigua."""

    matches: list[RecentMatchDTO] = Field(default_factory=list)
