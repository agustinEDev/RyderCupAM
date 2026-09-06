"""DTOs de estadísticas de jugador (BE #128)."""

# El DTO expone un campo llamado `date`, que sombrearia al tipo dentro de la
# clase: de ahi el alias
from datetime import date as date_type

from pydantic import BaseModel, ConfigDict, Field


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
    match_name: str | None = Field(
        default=None,
        description=(
            "El nombre que le puso quien creó la partida rápida. Nulo en un "
            "partido de torneo, que no tiene nombre propio: tiene el de su "
            "competición, y ese va en `tournament_name`."
        ),
    )
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
            "Puntos Stableford de la vuelta: 36 puntos es jugar a tu hándicap, "
            "así que es la única cifra que compara vueltas de medal, Stableford "
            "y match play entre sí. Se calcula en todos los formatos **menos "
            "foursomes**, donde la pareja juega una bola y no hay vuelta propia "
            "que puntuar: ahí siempre es None."
        ),
    )
    total_strokes: int | None = Field(
        default=None,
        description=(
            "Golpes brutos de los hoyos anotados. En **foursomes** son los del "
            "BANDO —una bola por hoyo, la anote quien la anote— y los mismos "
            "para los dos de la pareja, no los del jugador por su cuenta."
        ),
    )
    holes_played: int | None = Field(
        default=None, description="Cuántos hoyos se anotaron: 18 en vuelta entera, 9 en media"
    )
    partners: list[str] = Field(default_factory=list)
    opponents: list[str] = Field(default_factory=list)
    excluded_from_stats: bool = Field(
        default=False,
        description=(
            "True si el jugador ha dejado esta partida fuera de sus estadisticas. "
            "El historial la sigue enseñando —por eso viaja aqui la marca— pero el "
            "resumen de arriba no la cuenta: sin este campo, la pantalla enseñaria "
            "una vuelta que el resumen ignora y las dos cifras se contradirian sin "
            "explicacion. Los partidos de torneo son siempre False: la marca es solo "
            "de partidas rapidas."
        ),
    )


class RecentMatchesResponseDTO(BaseModel):
    """Historial de partidas del jugador, de la más reciente a la más antigua."""

    matches: list[RecentMatchDTO] = Field(default_factory=list)


# ============================================================================
# Desglose de golpes (BE #168)
# ============================================================================


class HoleDistributionDTO(BaseModel):
    """
    Cuántos hoyos acabaron en cada cesta, sobre el total contado.

    Se devuelven cuentas y no porcentajes: el porcentaje se saca dividiendo, y
    dar los dos invita a que dejen de cuadrar.
    """

    birdie_or_better: int = Field(0, description="Hoyos en birdie o mejor")
    par: int = Field(0, description="Hoyos en par")
    bogey: int = Field(0, description="Hoyos en bogey")
    double_or_worse: int = Field(0, description="Hoyos en doble bogey o peor")
    holes: int = Field(0, description="Hoyos contados en esta distribución")

    model_config = ConfigDict(from_attributes=True)


class ParPerformanceDTO(BaseModel):
    """Rendimiento en los hoyos de un par concreto."""

    par: int = Field(..., description="Par del hoyo (3, 4, 5 o 6)")
    holes: int = Field(..., description="Hoyos de ese par contados")
    average_to_par: float = Field(
        ..., description="Media neta respecto al par, POR HOYO (+0.8 = casi un golpe de más)"
    )

    model_config = ConfigDict(from_attributes=True)


class NinePerformanceDTO(BaseModel):
    """Rendimiento en una mitad de la vuelta."""

    holes: int = Field(..., description="Hoyos contados en esa mitad")
    average_to_par: float = Field(..., description="Media neta respecto al par, POR HOYO")

    model_config = ConfigDict(from_attributes=True)


class CoursePerformanceDTO(BaseModel):
    """Rendimiento en un campo, en la escala de una vuelta de 18."""

    golf_course_id: str = Field(..., description="ID del campo")
    golf_course_name: str | None = Field(None, description="Nombre del campo")
    rounds: int = Field(..., description="Vueltas contadas en ese campo")
    average_to_par: float = Field(
        ..., description="Media neta respecto al par por vuelta de 18, como `scoring_avg`"
    )

    model_config = ConfigDict(from_attributes=True)


class ScoringBreakdownResponseDTO(BaseModel):
    """
    Dónde gana y dónde pierde los golpes un jugador.

    `scoring_avg` dice cuánto juega de bien; esto dice dónde, que es lo que se
    puede llevar al campo de prácticas. Sale de las mismas tarjetas y de las
    mismas vueltas computables que la media, con el mismo tope de doble bogey
    neto: los dos números no pueden contar historias distintas.

    **Las medias van en dos escalas distintas, y es a propósito.** Por par y por
    mitad de vuelta son medias POR HOYO —escalar un par 3 a 18 hoyos no
    significa nada—; por campo va por vuelta de 18, que es la escala en la que
    ya se publica `scoring_avg` y con la que hay que poder compararla.

    La distribución se da **en bruto y en neto**: en bruto un birdie es un
    birdie, y en neto un jugador de hándicap alto ve los pares netos que hace
    en lugar de una lista de bogeys que no le dice dónde mejorar.

    Una cuenta sin vueltas devuelve ceros y listas vacías, no un 404.
    """

    holes_counted: int = Field(0, description="Hoyos contados en todo el desglose")
    rounds_counted: int = Field(0, description="Vueltas computables contadas")
    gross_distribution: HoleDistributionDTO = Field(
        default_factory=HoleDistributionDTO, description="Distribución en bruto"
    )
    net_distribution: HoleDistributionDTO = Field(
        default_factory=HoleDistributionDTO, description="Distribución en neto"
    )
    by_par: list[ParPerformanceDTO] = Field(
        default_factory=list,
        description="Una entrada por cada par jugado de verdad, de menor a mayor",
    )
    front_nine: NinePerformanceDTO | None = Field(None, description="Hoyos 1-9")
    back_nine: NinePerformanceDTO | None = Field(None, description="Hoyos 10-18")
    by_course: list[CoursePerformanceDTO] = Field(
        default_factory=list, description="Campos ordenados de mejor a peor media"
    )

    model_config = ConfigDict(from_attributes=True)
