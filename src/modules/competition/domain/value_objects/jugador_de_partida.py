"""
JugadorDePartida Value Object - Un jugador dentro de una partida de stroke play (#251).

Es la foto que se saca al generar (D14): su hándicap fijado, el de juego, sus
barras y los golpes que recibe en cada hoyo. Un cambio posterior del perfil no
la toca; se rehace al recalcular la partida.
"""

from dataclasses import dataclass
from decimal import Decimal

from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender

HOYOS = 18
# Como valida el hoyo del campo (`Hole`)
PAR_MINIMO, PAR_MAXIMO = 3, 6


@dataclass(frozen=True)
class JugadorDePartida:
    """
    Atributos:
        user_id: El jugador
        handicap: Su hándicap fijado al cerrar (el personalizado si lo tiene)
        playing_handicap: Su hándicap de juego, con signo (un plus es negativo)
        tee_color: Las barras desde las que sale
        tee_gender: El género de esas barras
        golpes_por_hoyo: Los 18 hoyos en orden, con signo: lo que recibe (o da) en cada uno
        par_por_hoyo: El par de cada hoyo desde SUS barras (P12): 25 campos tienen par
            distinto por barra, y si alguien edita el campo no cambian los resultados
    """

    user_id: UserId
    handicap: Decimal
    playing_handicap: int
    tee_color: TeeColor
    tee_gender: Gender | None
    golpes_por_hoyo: tuple[int, ...]
    par_por_hoyo: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.golpes_por_hoyo) != HOYOS:
            raise ValueError(
                f"Los golpes van hoyo a hoyo: {HOYOS}, no {len(self.golpes_por_hoyo)}."
            )
        if sum(self.golpes_por_hoyo) != self.playing_handicap:
            raise ValueError("Los golpes por hoyo tienen que sumar el hándicap de juego.")
        if len(self.par_por_hoyo) != HOYOS or not all(
            PAR_MINIMO <= par <= PAR_MAXIMO for par in self.par_por_hoyo
        ):
            raise ValueError(f"El par va hoyo a hoyo: {HOYOS}, de {PAR_MINIMO} a {PAR_MAXIMO}.")
