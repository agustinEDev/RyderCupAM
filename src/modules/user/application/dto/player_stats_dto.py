"""DTOs de estadísticas de jugador (BE #128)."""

# El DTO expone un campo llamado `date`, que sombrearia al tipo dentro de la
# clase: de ahi el alias
from datetime import date as date_type

from pydantic import BaseModel, Field


class PlayerStatsResponseDTO(BaseModel):
    """
    Resumen de rendimiento de un jugador, para el panel.

    Solo cuentan las vueltas enteras de partidas terminadas, de partida rápida
    y de torneo. Una tarjeta a la que le falta un hoyo no entra ni en la media
    ni en `rounds_played`: los dos números hablan siempre de las mismas rondas.

    `scoring_avg` es la media de golpes netos respecto al par, no de golpes
    brutos: comparar brutos entre campos y hándicaps distintos no dice nada.
    Cada hoyo va topado en el net double bogey (Regla WHS 3.1). Va en None
    cuando no hay ninguna vuelta computable, que no es lo mismo que una media
    de cero.

    Los campos de diferencial (BE #167) se calculan sobre un subconjunto de
    esas vueltas: solo las jugadas desde un tee conocido, porque sin Slope ni
    Course Rating no hay diferencial. De ahí que `rounds_with_differential`
    pueda ser menor que `rounds_played`; la interfaz debería decirlo cuando no
    coincidan, en lugar de dar a entender que el índice mira todas las vueltas.

    **El índice estimado no es el oficial de la federación.** Le falta el PCC,
    el ajuste por las condiciones de juego de cada jornada, que solo puede
    calcular quien tiene todas las tarjetas del día. Conviene que la interfaz
    lo diga para no crear la expectativa equivocada.
    """

    handicap: float | None = Field(
        default=None, description="El hándicap oficial que el jugador tiene en su perfil"
    )
    handicap_trend: float | None = Field(
        default=None,
        description=(
            "Cambio entre las 5 vueltas más recientes y las 5 anteriores. "
            "**Negativo es mejorar**, igual que baja un hándicap. None hasta "
            "que haya 10 vueltas con diferencial que comparar."
        ),
    )
    scoring_avg: float | None = None
    rounds_played: int = 0
    tournaments_total: int = 0
    tournaments_active: int = 0
    estimated_index: float | None = Field(
        default=None,
        description=(
            "A qué hándicap está jugando: media de sus mejores diferenciales "
            "recientes según la tabla WHS 5.2. None con menos de 3 vueltas."
        ),
    )
    playing_avg: float | None = Field(
        default=None,
        description=(
            "Media de todos los diferenciales recientes, no solo de los mejores. "
            "Suele ser varios golpes peor que el índice: ese mira de lo que el "
            "jugador es capaz, este a lo que juega de media."
        ),
    )
    best_differential: float | None = Field(
        default=None,
        description=(
            "El mejor diferencial del registro: su mejor vuelta entre las 20 "
            "más recientes, que son las que el WHS mira."
        ),
    )
    rounds_with_differential: int = Field(
        default=0,
        description=(
            "Cuántas de las vueltas computadas tienen diferencial. Menor que "
            "`rounds_played` cuando alguna se jugó sin registrar el tee. Puede "
            "superar los 20 de la ventana: cuenta las que hay, no las que se miran."
        ),
    )
    differentials: list[float] = Field(
        default_factory=list,
        description=(
            "Los 20 diferenciales más recientes, del más nuevo al más antiguo, "
            "para pintar la tendencia. Es la misma ventana sobre la que se "
            "calculan el índice, la media y la mejor vuelta."
        ),
    )


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
    stableford_points: int | None = Field(
        default=None,
        description=(
            "Puntos Stableford de la vuelta, **calculados en cualquier formato**: "
            "36 puntos es jugar a tu hándicap, así que es la única cifra que "
            "compara vueltas de medal, Stableford y match play entre sí."
        ),
    )
    total_strokes: int | None = Field(
        default=None, description="Golpes brutos de los hoyos anotados"
    )
    holes_played: int | None = Field(
        default=None, description="Cuántos hoyos se anotaron: 18 en vuelta entera, 9 en media"
    )
    partners: list[str] = Field(default_factory=list)
    opponents: list[str] = Field(default_factory=list)


class RecentMatchesResponseDTO(BaseModel):
    """Historial de partidas del jugador, de la más reciente a la más antigua."""

    matches: list[RecentMatchDTO] = Field(default_factory=list)
