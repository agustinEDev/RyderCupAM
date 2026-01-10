"""
CompetitionName Value Object - Nombre válido y normalizado de una competición.

Este Value Object representa el nombre de una competición de golf.
Aplica validaciones de negocio y normalización automática.
"""

from dataclasses import dataclass

# Constantes de validación
MAX_COMPETITION_NAME_LENGTH = 100


class InvalidCompetitionNameError(Exception):
    """Excepción lanzada cuando el nombre de una competición no es válido."""

    pass


@dataclass(frozen=True)
class CompetitionName:
    """
    Value Object para nombres de competición.

    Inmutable y validado automáticamente.
    Aplica capitalización (Title Case) para mantener consistencia.

    Reglas de negocio:
    - No puede estar vacío
    - Máximo 100 caracteres
    - Se normaliza aplicando capitalización

    Ejemplos:
        >>> name = CompetitionName("ryder cup 2025")
        >>> print(name.value)
        'Ryder Cup 2025'

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

        # 1. Normalizar: eliminar espacios en blanco al inicio/final
        normalized_name = self.value.strip()

        # 2. Validar que no esté vacío
        if not normalized_name:
            raise InvalidCompetitionNameError(
                "El nombre de la competición no puede estar vacío"
            )

        # 3. Validar longitud máxima
        if len(normalized_name) > MAX_COMPETITION_NAME_LENGTH:
            raise InvalidCompetitionNameError(
                f"El nombre de la competición no puede exceder {MAX_COMPETITION_NAME_LENGTH} caracteres. "
                f"Longitud actual: {len(normalized_name)}"
            )

        # 4. Aplicar capitalización (Title Case)
        # Cada palabra comienza con mayúscula
        capitalized_name = normalized_name.title()

        # 5. Asignar el valor normalizado y validado
        # Usar object.__setattr__ porque la clase es frozen
        object.__setattr__(self, "value", capitalized_name)

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
