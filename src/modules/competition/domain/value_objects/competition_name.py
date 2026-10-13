"""
CompetitionName Value Object - Nombre válido y normalizado de una competición.

Este Value Object representa el nombre de una competición de golf.
Aplica validaciones de negocio y normalización automática.
"""

import re
import unicodedata
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


def _sin_etiquetas(texto: str) -> str:
    """Hasta que no quede ninguna: anidadas, una pasada dejaba un `<script>` (/code-review)."""
    while (limpio := _ETIQUETA.sub("", texto)) != texto:
        texto = limpio
    return texto


def _se_lee(texto: str) -> bool:
    """Alguna letra o cifra de verdad: «ㅤㅤㅤ» (relleno Hangul) o «...» no son un nombre."""
    return any(c != "\u3164" and unicodedata.category(c)[0] in ("L", "N") for c in texto)


def _sin_invisibles(texto: str) -> str:
    """Fuera los de control y los de formato (anchura cero, dirección): Cc y Cf.

    Los espacios en blanco se quedan: luego se normalizan a uno solo.
    """
    return "".join(c for c in texto if c.isspace() or unicodedata.category(c) not in ("Cc", "Cf"))


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
        # Primero los invisibles: uno entre `<` y `script` escondía la etiqueta y,
        # quitado después, la recomponía (revisor)
        sin_html = _sin_etiquetas(_sin_invisibles(self.value))
        # 2. Normalizar los espacios: fuera los de los extremos y uno solo dentro
        normalized_name = " ".join(sin_html.split())

        # 3. Validar que no esté vacío
        if not normalized_name:
            raise InvalidCompetitionNameError("El nombre de la competición no puede estar vacío")

        # 4. Validar longitud mínima, ya limpio: «<b>ab</b>» se quedaría en «ab»;
        #    y con algo que se lea: una letra o una cifra (no solo rellenos)
        if len(normalized_name) < MIN_COMPETITION_NAME_LENGTH:
            raise InvalidCompetitionNameError(
                f"El nombre de la competición necesita al menos {MIN_COMPETITION_NAME_LENGTH} "
                "caracteres."
            )
        if not _se_lee(normalized_name):
            raise InvalidCompetitionNameError(
                "El nombre de la competición necesita alguna letra o cifra."
            )

        # 5. Validar longitud máxima
        if len(normalized_name) > MAX_COMPETITION_NAME_LENGTH:
            raise InvalidCompetitionNameError(
                f"El nombre de la competición no puede exceder {MAX_COMPETITION_NAME_LENGTH} caracteres. "
                f"Longitud actual: {len(normalized_name)}"
            )

        # 6. Tal cual lo escribió el organizador: «RCG El Prat», «Copa McGregor» (#540)
        object.__setattr__(self, "value", normalized_name)

    @classmethod
    def guardado(cls, valor: str) -> "CompetitionName":
        """
        El nombre tal como está en la base de datos, sin volver a validarlo: lo
        guardado con las reglas de antes (con title()) no puede romper la carga.
        """
        nombre = object.__new__(cls)
        object.__setattr__(nombre, "value", valor)
        return nombre

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
