"""
Hole Entity - Hoyo individual de un campo de golf.
"""

from dataclasses import dataclass

MIN_HOLE_NUMBER = 1
MAX_HOLE_NUMBER = 18
VALID_PARS = (3, 4, 5, 6)
MIN_METERS = 20
MAX_METERS = 700


@dataclass
class Hole:
    """
    Hoyo de un campo de golf, tal y como se juega desde una salida concreta.

    Los hoyos cuelgan del Tee y no del campo, porque el par, el índice de
    dificultad y la distancia dependen de la barra desde la que se juega. En
    los campos federados españoles esto ocurre en 77 de 802 recorridos, y en la
    mayoría la diferencia es entre colores del mismo género, no entre géneros.

    Attributes:
        number: Número del hoyo (1-18)
        par: Par del hoyo (3-6)
        stroke_index: Índice de dificultad (1-18, único dentro de la salida)
        meters: Distancia en metros desde esta salida (opcional)

    Example:
        >>> hole = Hole(number=1, par=4, stroke_index=5, meters=351)
    """

    number: int
    par: int
    stroke_index: int
    meters: int | None = None

    def __post_init__(self) -> None:
        """Valida los valores del hoyo."""
        if not (MIN_HOLE_NUMBER <= self.number <= MAX_HOLE_NUMBER):
            raise ValueError(
                f"Hole number must be between {MIN_HOLE_NUMBER} and "
                f"{MAX_HOLE_NUMBER}, got {self.number}"
            )

        if self.par not in VALID_PARS:
            raise ValueError(
                f"Par must be one of {', '.join(str(p) for p in VALID_PARS)}, got {self.par}"
            )

        if not (MIN_HOLE_NUMBER <= self.stroke_index <= MAX_HOLE_NUMBER):
            raise ValueError(
                f"Stroke index must be between {MIN_HOLE_NUMBER} and "
                f"{MAX_HOLE_NUMBER}, got {self.stroke_index}"
            )

        if self.meters is not None and not (MIN_METERS <= self.meters <= MAX_METERS):
            raise ValueError(
                f"Meters must be between {MIN_METERS} and {MAX_METERS}, got {self.meters}"
            )
