"""
HandicapSettings Value Object - Configuración general de hándicap para una competición.

Este Value Object representa la POLÍTICA general de hándicap del torneo.
NO calcula el hándicap de juego real (que depende de Course Rating, Slope, formato, etc.).

El cálculo completo del hándicap de juego se realizará en el módulo 'matches' considerando:
1. Handicap Index del jugador
2. Course Rating y Slope Rating del campo
3. Formato de la partida (Stroke Play, Four-Ball, Foursomes, etc.)
4. Factor de competición específico (100%, 90%, 50%, etc.)
"""

from dataclasses import dataclass
from enum import Enum


class HandicapType(str, Enum):
    """
    Enum para los tipos de política de hándicap disponibles.

    - SCRATCH: Torneo scratch (sin aplicar hándicap). Para jugadores de nivel similar.
    - PERCENTAGE: Torneo con hándicap. Se aplicará un porcentaje del Course Handicap.
    """
    SCRATCH = "SCRATCH"
    PERCENTAGE = "PERCENTAGE"


class InvalidHandicapSettingsError(Exception):
    """Excepción lanzada cuando la configuración de hándicap no es válida."""
    pass


@dataclass(frozen=True)
class HandicapSettings:
    """
    Value Object para configuración general de hándicap.

    Inmutable y validado automáticamente.
    Representa la POLÍTICA del torneo, no el cálculo final.

    Reglas de negocio:
    - Si type es SCRATCH, percentage debe ser None (no se usa hándicap)
    - Si type es PERCENTAGE, percentage debe ser 90, 95 o 100
    - Solo se permiten esos tres porcentajes estándar del WHS

    IMPORTANTE:
    Este VO solo define la configuración general del torneo.
    El cálculo real del Playing Handicap se hará en cada Match considerando:
    - Course Handicap = (Handicap Index x Slope Rating / 113) + (Course Rating - Par)
    - Playing Handicap = Course Handicap x Allowance Factor (según formato)

    Ejemplos:
        >>> # Torneo scratch (sin hándicap) - Para jugadores de nivel similar
        >>> settings1 = HandicapSettings(HandicapType.SCRATCH, None)

        >>> # Torneo con hándicap al 90% - Configuración común en Four-Ball
        >>> settings2 = HandicapSettings(HandicapType.PERCENTAGE, 90)

        >>> # Torneo con hándicap al 100% - Stroke Play individual
        >>> settings3 = HandicapSettings(HandicapType.PERCENTAGE, 100)

        >>> # Inválido: SCRATCH con porcentaje
        >>> HandicapSettings(HandicapType.SCRATCH, 90)  # Lanza InvalidHandicapSettingsError

        >>> # Inválido: PERCENTAGE con porcentaje no permitido
        >>> HandicapSettings(HandicapType.PERCENTAGE, 85)  # Lanza InvalidHandicapSettingsError
    """

    type: HandicapType
    percentage: int | None

    def __post_init__(self):
        """
        Validación automática de la configuración de hándicap.

        Valida la consistencia entre tipo y porcentaje según reglas de negocio.
        """
        # 1. Validar tipo
        if not isinstance(self.type, HandicapType):
            raise InvalidHandicapSettingsError(
                f"El tipo debe ser HandicapType.SCRATCH o HandicapType.PERCENTAGE, "
                f"se recibió {type(self.type).__name__}"
            )

        # 2. Validar reglas específicas según el tipo
        if self.type == HandicapType.SCRATCH:
            # SCRATCH no debe tener porcentaje
            if self.percentage is not None:
                raise InvalidHandicapSettingsError(
                    "Para tipo SCRATCH, el porcentaje debe ser None"
                )

        elif self.type == HandicapType.PERCENTAGE:
            # PERCENTAGE debe tener un porcentaje válido
            if self.percentage is None:
                raise InvalidHandicapSettingsError(
                    "Para tipo PERCENTAGE, el porcentaje es obligatorio"
                )

            # Solo se permiten 90, 95 o 100 (porcentajes estándar WHS)
            allowed_percentages = {90, 95, 100}
            if self.percentage not in allowed_percentages:
                raise InvalidHandicapSettingsError(
                    f"El porcentaje debe ser uno de {allowed_percentages}, "
                    f"se recibió {self.percentage}"
                )

    def is_scratch(self) -> bool:
        """
        Verifica si el torneo es tipo SCRATCH (sin hándicap).

        Returns:
            bool: True si es SCRATCH, False si es PERCENTAGE
        """
        return self.type == HandicapType.SCRATCH

    def allows_handicap(self) -> bool:
        """
        Verifica si el torneo permite usar hándicap.

        Returns:
            bool: True si permite hándicap (PERCENTAGE), False si es scratch
        """
        return self.type == HandicapType.PERCENTAGE

    def get_allowance_percentage(self) -> int | None:
        """
        Obtiene el porcentaje de allowance configurado.

        Este porcentaje es la configuración general del torneo.
        En cada match se aplicará según el formato específico.

        Returns:
            Optional[int]: El porcentaje (90, 95, 100) o None si es SCRATCH

        Ejemplos:
            >>> settings = HandicapSettings(HandicapType.PERCENTAGE, 90)
            >>> settings.get_allowance_percentage()
            90

            >>> settings_scratch = HandicapSettings(HandicapType.SCRATCH, None)
            >>> settings_scratch.get_allowance_percentage()
            None
        """
        return self.percentage

    def __str__(self) -> str:
        """Representación string legible."""
        if self.is_scratch():
            return "SCRATCH (No Handicap)"
        return f"PERCENTAGE {self.percentage}%"

    def __eq__(self, other) -> bool:
        """
        Operador de igualdad - Comparación por valor.

        Dos HandicapSettings son iguales si tienen el mismo tipo y porcentaje.
        """
        return (
            isinstance(other, HandicapSettings) and
            self.type == other.type and
            self.percentage == other.percentage
        )

    def __hash__(self) -> int:
        """Hash del objeto - Permite usar en sets y como keys de dict."""
        return hash((self.type, self.percentage))

    def __composite_values__(self):
        """
        Retorna los valores para SQLAlchemy composite mapping.

        Requerido para que SQLAlchemy pueda persistir el Value Object.
        """
        return (self.type.value, self.percentage)
