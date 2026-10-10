"""
StrokePlaySetup Value Object - Lo que es solo del stroke play (RyderCupAM#251).

La hermana de `RyderCupSetup`: un Stableford o un Medal la tiene y una Ryder no.
Decidido con Agustín el 6 oct 2026:

- **Categorías por límites superiores** de hándicap: 12,0 y 26,0 son «hasta
  12,0», «de 12,1 a 26,0» y «más de 26,0». Hasta cinco categorías. Solo cuentan
  en la clasificación neta.
- **Jornadas por jugador**: como mucho una franja por jornada, y el organizador
  fija en cuántas jornadas juega cada uno (normalmente una).
- **La general**: acumulada o mejor tarjeta, a elección del organizador.
- **Categorías iguales** (10 oct 2026): en vez de escribir los límites, el
  organizador pide N categorías y los límites salen al cerrar las inscripciones,
  con los hándicaps fijados: grupos lo más parecidos posible, y los empatados en
  una frontera van todos a la de hándicap más bajo.

**Es inmutable**, por lo mismo que la de la Ryder: se guarda en columnas de
`competitions` con `composite()`, y SQLAlchemy no ve un cambio hecho dentro.
Cada cambio devuelve una pieza nueva.
"""

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise
from typing import Self, overload

from src.modules.user.domain.value_objects.user_id import UserId

from .overall_standing import OverallStanding

MAX_CATEGORIES = 5
# Pedir una sola categoría iguales es no tener categorías: eso son límites vacíos
MIN_CATEGORY_COUNT = 2
# Una categoría se disputa con 6 jugadores como mínimo, como en la RFEG (7 oct 2026)
MIN_JUGADORES_POR_CATEGORIA = 6
MIN_LIMIT = Decimal("-10.0")
MAX_LIMIT = Decimal("54.0")
UNA_DECIMAL = Decimal("0.1")


@overload
def handicap_fijado(handicap: Decimal) -> Decimal: ...
@overload
def handicap_fijado(handicap: None) -> None: ...
def handicap_fijado(handicap: Decimal | None) -> Decimal | None:
    """
    El hándicap que se fija al cerrar, con un decimal: lo que guarda la columna.

    Un perfil puede traer centésimos, y la categoría y el reparto tienen que
    salir del mismo valor que queda guardado. Redondea hacia fuera en el medio,
    como Postgres al guardar en `Numeric(4, 1)`.
    """
    if handicap is None:
        return None
    return handicap.quantize(UNA_DECIMAL, rounding=ROUND_HALF_UP)


class StrokePlaySettingsError(ValueError):
    """Unos ajustes de stroke play que no tienen sentido, con el motivo."""

    pass


@dataclass(frozen=True)
class StrokePlaySetup:
    """Categorías, jornadas por jugador y regla de la general de un stroke play."""

    category_limits: tuple[Decimal, ...] = ()
    max_matchdays_per_player: int = 1
    overall_standing: OverallStanding = OverallStanding.ACCUMULATED
    # Categorías iguales: cuántas se piden. None = límites a mano. Con él, los
    # límites están vacíos hasta el cierre, que los calcula (`repartir`)
    category_count: int | None = None

    def __post_init__(self) -> None:
        self._check_limits(self.category_limits)
        self._check_count(self.category_count)
        if self.max_matchdays_per_player < 1:
            raise StrokePlaySettingsError("Cada jugador tiene que poder jugar al menos una jornada")

    # ------------------------------------------------------------------
    # Creación y cambios
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        category_limits: Sequence[Decimal] | None = None,
        max_matchdays_per_player: int | None = None,
        overall_standing: OverallStanding | None = None,
        category_count: int | None = None,
    ) -> Self:
        """Unos ajustes nuevos; lo que no llega se queda con su valor por defecto."""
        return cls().with_changes(
            category_limits=category_limits,
            max_matchdays_per_player=max_matchdays_per_player,
            overall_standing=overall_standing,
            category_count=category_count,
        )

    def with_changes(
        self,
        category_limits: Sequence[Decimal] | None = None,
        max_matchdays_per_player: int | None = None,
        overall_standing: OverallStanding | None = None,
        category_count: int | None = None,
    ) -> Self:
        """
        Una pieza nueva con lo que cambia; None es «no lo toques».

        Una lista de límites vacía SÍ es un cambio: quita las categorías. Los
        límites y el contador son los dos modos de hacer categorías: mandar uno
        cambia a ese modo y borra el otro, y los dos a la vez no se entienden.
        """
        if category_limits is not None and category_count is not None:
            raise StrokePlaySettingsError(
                "Las categorías se hacen con límites o con un número de categorías "
                "iguales, no con las dos cosas a la vez"
            )
        limites, contador = self.category_limits, self.category_count
        if category_limits is not None:
            limites, contador = tuple(self._con_un_decimal(v) for v in category_limits), None
        elif category_count is not None:
            limites, contador = (), category_count
        return replace(
            self,
            category_limits=limites,
            category_count=contador,
            max_matchdays_per_player=(
                max_matchdays_per_player
                if max_matchdays_per_player is not None
                else self.max_matchdays_per_player
            ),
            overall_standing=overall_standing or self.overall_standing,
        )

    def repartir(self, handicaps: Iterable[Decimal | None]) -> Self:
        """
        Los límites de las categorías iguales, con los hándicaps fijados al cerrar.

        Decidido con Agustín el 10 oct 2026:

        - Se parte en tantas como quepan con 6 por categoría (14 para 3 → 2 de 7).
        - Cada frontera cae donde quedarían grupos iguales (k·n/N, redondeado) y
          el límite es el hándicap del último de ese grupo: con «hasta X»
          incluido, los que empatan con él van todos a la de hándicap más bajo.
        - Si así una categoría quedaría vacía (el empate llega hasta arriba o
          hasta la frontera anterior), la frontera baja justo por debajo del
          empate y los empatados suben juntos; si tampoco cabe, sale una menos.

        Con el hándicap a un decimal, el que se fija. Quien no tiene no cuenta.
        Después, como siempre, la regla de los seis. A mano no se reparte nada.
        """
        if self.category_count is None:
            return self
        orden = sorted(handicap_fijado(h) for h in handicaps if h is not None)
        n = len(orden)
        total = min(self.category_count, n // MIN_JUGADORES_POR_CATEGORIA)
        limites: list[Decimal] = []
        for k in range(1, total):
            # Redondeo hacia arriba en el medio: k·n/N con enteros, sin flotantes
            cuantos = (2 * k * n + total) // (2 * total)
            limite = self._frontera(orden, orden[cuantos - 1], limites[-1] if limites else None)
            if limite is not None:
                limites.append(limite)
        return replace(self, category_limits=tuple(limites))

    @staticmethod
    def _frontera(
        orden: list[Decimal], limite: Decimal, anterior: Decimal | None
    ) -> Decimal | None:
        """
        El límite, o el hándicap justo por debajo del empate si con él una
        categoría quedaría vacía; None si no cabe ninguno.
        """

        def deja_las_dos_con_alguien(valor: Decimal) -> bool:
            return valor < orden[-1] and (anterior is None or valor > anterior)

        if deja_las_dos_con_alguien(limite):
            return limite
        debajo = [h for h in orden if h < limite]
        if debajo and deja_las_dos_con_alguien(debajo[-1]):
            return debajo[-1]
        return None

    def sin_reparto(self) -> Self:
        """Las categorías iguales sin los límites del último cierre (al reabrir)."""
        if self.category_count is None:
            return self
        return replace(self, category_limits=())

    # ------------------------------------------------------------------
    # Reglas
    # ------------------------------------------------------------------

    @property
    def number_of_categories(self) -> int:
        """Cuántas categorías salen de los límites: uno más que límites."""
        return len(self.category_limits) + 1

    def category_for(self, handicap: Decimal | None) -> int | None:
        """
        La categoría (1, 2, 3…) de un hándicap; «hasta 12,0» incluye el 12,0.

        Sin hándicap no hay categoría (1c): solo pasa si alguien se lo quitó
        después de cerrar las inscripciones y la competición arrancó sola.
        """
        if handicap is None:
            return None
        # Con un decimal, el que queda fijado: un 12,04 es «hasta 12,0»
        fijado = handicap_fijado(handicap)
        return 1 + sum(1 for limite in self.category_limits if fijado > limite)

    def categorias(self, handicaps: Mapping[UserId, Decimal | None]) -> dict[UserId, int | None]:
        """
        La categoría de cada jugador, con la regla de los seis (7 oct 2026).

        Una categoría con menos de 6 jugadores se une a la contigua de hándicap
        más bajo (la 1.ª, que no tiene, a la 2.ª), empezando por la de hándicap
        más alto, y se repite hasta que todas tengan 6 o quede una sola. Las que quedan se numeran 1, 2, 3… Quien no
        tiene hándicap no tiene categoría ni cuenta para el mínimo.
        """
        grupos = [[n] for n in range(1, self.number_of_categories + 1)]
        nominal = {u: self.category_for(h) for u, h in handicaps.items()}
        por_categoria = Counter(c for c in nominal.values() if c is not None)

        def jugadores(grupo: list[int]) -> int:
            return sum(por_categoria[c] for c in grupo)

        while len(grupos) > 1:
            # Desde la de hándicap más alto: los pocos de abajo se van juntando
            # hacia arriba, y así se conservan más categorías
            pequeno = next(
                (
                    i
                    for i in range(len(grupos) - 1, -1, -1)
                    if jugadores(grupos[i]) < MIN_JUGADORES_POR_CATEGORIA
                ),
                None,
            )
            if pequeno is None:
                break
            destino = pequeno - 1 if pequeno > 0 else 1
            grupos[destino] = sorted(grupos[destino] + grupos[pequeno])
            del grupos[pequeno]

        efectiva = {c: i + 1 for i, grupo in enumerate(grupos) for c in grupo}
        return {u: (efectiva[c] if c is not None else None) for u, c in nominal.items()}

    def check_fits_in(self, days: int) -> None:
        """
        Las jornadas de cada jugador caben en el torneo: una franja por jornada,
        así que no puede jugar más jornadas que días tiene.

        Raises:
            StrokePlaySettingsError: Si no caben
        """
        if self.max_matchdays_per_player > days:
            raise StrokePlaySettingsError(
                f"Cada jugador puede jugar {self.max_matchdays_per_player} jornadas, "
                f"pero el torneo dura {days} días"
            )

    @staticmethod
    def _con_un_decimal(limite: Decimal) -> Decimal:
        """
        «12» se guarda como «12.0», que es como vuelve de la base de datos.

        Solo si ya tiene un decimal como mucho: redondear un «12.05» lo dejaría
        pasar como otro número, y tiene que rechazarse.
        """
        # Lo que no es un hándicap se deja tal cual para que lo rechace el rango:
        # cuantizar un 1E+50 o un NaN lanza InvalidOperation, que no es un
        # ValueError y acabaría en un 500 (CodeRabbit, #501)
        if not StrokePlaySetup._es_un_handicap(limite):
            return limite
        con_uno = limite.quantize(UNA_DECIMAL)
        return con_uno if con_uno == limite else limite

    @staticmethod
    def _es_un_handicap(limite: Decimal) -> bool:
        """Un número finito dentro del rango de hándicap."""
        return limite.is_finite() and MIN_LIMIT <= limite <= MAX_LIMIT

    @staticmethod
    def _check_count(count: object) -> None:
        # Un `bool` es un `int` en Python, pero True vale 1 y se queda fuera del rango
        if count is None:
            return
        if not isinstance(count, int) or not MIN_CATEGORY_COUNT <= count <= MAX_CATEGORIES:
            raise StrokePlaySettingsError(
                f"Las categorías iguales son entre {MIN_CATEGORY_COUNT} y {MAX_CATEGORIES}"
            )

    @staticmethod
    def _check_limits(limits: tuple[Decimal, ...]) -> None:
        if len(limits) > MAX_CATEGORIES - 1:
            raise StrokePlaySettingsError(
                f"Como mucho {MAX_CATEGORIES} categorías: {MAX_CATEGORIES - 1} límites"
            )
        for limite in limits:
            if not StrokePlaySetup._es_un_handicap(limite):
                raise StrokePlaySettingsError(
                    "Los límites de categoría son hándicaps: entre -10,0 y 54,0"
                )
            if limite != limite.quantize(UNA_DECIMAL):
                raise StrokePlaySettingsError(
                    "Los límites de categoría llevan un decimal como mucho"
                )
        if any(a >= b for a, b in pairwise(limits)):
            raise StrokePlaySettingsError(
                "Los límites de categoría van de menor a mayor y sin repetirse"
            )

    # ------------------------------------------------------------------
    # Persistencia, con composite()
    # ------------------------------------------------------------------

    def __composite_values__(self) -> tuple:
        """En el orden de `from_columns`: así se guarda en `competitions`."""
        return (
            list(self.category_limits),
            self.max_matchdays_per_player,
            self.overall_standing,
            self.category_count,
        )

    @classmethod
    def from_columns(
        cls,
        category_limits: Sequence[Decimal] | None,
        max_matchdays_per_player: int | None,
        overall_standing: object,
        category_count: int | None = None,
    ) -> Self | None:
        """
        Reconstruye la pieza al leer. Sin jornadas guardadas no es un stroke play: None.

        No valida: lo guardado ya pasó la validación al crearse, y una lectura
        no debe tumbar la carga de un torneo.
        """
        if max_matchdays_per_player is None:
            return None
        pieza = object.__new__(cls)
        object.__setattr__(
            pieza, "category_limits", tuple(Decimal(str(v)) for v in category_limits or ())
        )
        object.__setattr__(pieza, "max_matchdays_per_player", max_matchdays_per_player)
        object.__setattr__(
            pieza,
            "overall_standing",
            OverallStanding(str(overall_standing))
            if overall_standing
            else OverallStanding.ACCUMULATED,
        )
        object.__setattr__(pieza, "category_count", category_count)
        return pieza
