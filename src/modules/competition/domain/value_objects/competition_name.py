"""
CompetitionName Value Object - Nombre válido y normalizado de una competición.

Este Value Object representa el nombre de una competición de golf.
Aplica validaciones de negocio y normalización automática.
"""

import re
from dataclasses import dataclass

# Constantes de validación
MIN_COMPETITION_NAME_LENGTH = 3
MAX_COMPETITION_NAME_LENGTH = 100


class InvalidCompetitionNameError(ValueError):
    """Excepción lanzada cuando el nombre de una competición no es válido."""

    pass


# Solo etiquetas de verdad (`<b>`, `</script>`, `<img src=x>`): «Hcp < 10» o
# «Copa <3 amigos>» no lo son. [^<>]* sin retroceso polinómico (ReDoS)
_ETIQUETA = re.compile(r"</?[A-Za-z][^<>]*>")
_CONTROL = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


@dataclass(frozen=True)
class CompetitionName:
    """
    Value Object para nombres de competición.

    Inmutable y validado automáticamente.

    Reglas de negocio:
    - No puede estar vacío
    - Máximo 100 caracteres
    - Se guarda tal cual lo escribe el organizador, sin etiquetas HTML ni
      caracteres de control y con los espacios normalizados (#540); para no
      repetir nombre se compara sin mayúsculas

    Ejemplos:
        >>> name = CompetitionName("  RCG  El Prat ")
        >>> print(name.value)
        'RCG El Prat'

        >>> CompetitionName("")  # Lanza InvalidCompetitionNameError
    """

    value: str

    def __post_init__(self):
        """
        Validación y normalización automática.

        Se ejecuta automáticamente después de __init__.
        Usamos object.__setattr__ porque la clase es frozen (inmutable).
        """
        if not isinstance(self.value, str):
            raise InvalidCompetitionNameError("El nombre debe ser un string")

        # 1. Fuera etiquetas HTML y caracteres de control (#540: sin title(), el
        #    `<script>` ya no salía disfrazado de `<Script>`), sin escapar el `&`
        sin_html = _CONTROL.sub("", _ETIQUETA.sub("", self.value))
        # 2. Normalizar los espacios: fuera los de los extremos y uno solo dentro
        normalized_name = " ".join(sin_html.split())

        # 3. Validar que no esté vacío
        if not normalized_name:
            raise InvalidCompetitionNameError("El nombre de la competición no puede estar vacío")

        # 4. Validar longitud mínima, ya limpio: «<b>ab</b>» se quedaría en «ab»
        if len(normalized_name) < MIN_COMPETITION_NAME_LENGTH:
            raise InvalidCompetitionNameError(
                f"El nombre de la competición necesita al menos {MIN_COMPETITION_NAME_LENGTH} "
                "caracteres."
            )

        # 5. Validar longitud máxima
        if len(normalized_name) > MAX_COMPETITION_NAME_LENGTH:
            raise InvalidCompetitionNameError(
                f"El nombre de la competición no puede exceder {MAX_COMPETITION_NAME_LENGTH} caracteres. "
                f"Longitud actual: {len(normalized_name)}"
            )

        # 6. Tal cual lo escribió el organizador: «RCG El Prat», «Copa McGregor» (#540)
        object.__setattr__(self, "value", normalized_name)

    @property
    def clave(self) -> str:
        """Para no repetir nombre: sin distinguir mayúsculas (#540)."""
        return self.value.lower()

    def __str__(self) -> str:
        """Representación string legible."""
        return self.value

    def __eq__(self, other) -> bool:
        """
        Operador de igualdad - Comparación por valor.

        Dos CompetitionName son iguales si tienen el mismo valor.
        """
        return isinstance(other, CompetitionName) and self.value == other.value

    def __hash__(self) -> int:
        """
        Hash del objeto - Permite usar en sets y como keys de dict.

        Requerido porque definimos __eq__ en un frozen dataclass.
        """
        return hash(self.value)

    def __composite_values__(self):
        """
        Retorna los valores para SQLAlchemy composite mapping.

        Requerido para que SQLAlchemy pueda persistir el Value Object.
        """
        return (self.value,)
