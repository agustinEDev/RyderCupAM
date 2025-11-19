# -*- coding: utf-8 -*-
"""
DateRange Value Object - Rango de fechas válido para una competición.

Este Value Object representa un período de tiempo definido por fecha de inicio y fin.
Garantiza que el rango sea lógicamente válido.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Union


class InvalidDateRangeError(Exception):
    """Excepción lanzada cuando un rango de fechas no es válido."""
    pass


@dataclass(frozen=True)
class DateRange:
    """
    Value Object para rangos de fechas.

    Inmutable y validado automáticamente.
    Garantiza que start_date <= end_date.

    Reglas de negocio:
    - Ambas fechas son requeridas
    - start_date debe ser menor o igual que end_date
    - Las fechas pueden ser date o datetime (se normalizan a date)

    Ejemplos:
        >>> from datetime import date
        >>> range1 = DateRange(date(2025, 6, 1), date(2025, 6, 3))
        >>> range1.duration_days()
        2

        >>> DateRange(date(2025, 6, 3), date(2025, 6, 1))  # Lanza InvalidDateRangeError
    """

    start_date: date
    end_date: date

    def __post_init__(self):
        """
        Validación automática del rango de fechas.

        Normaliza datetime a date si es necesario y valida la lógica del rango.
        """
        # 1. Validar que las fechas no sean None
        if self.start_date is None:
            raise InvalidDateRangeError("La fecha de inicio no puede ser None")

        if self.end_date is None:
            raise InvalidDateRangeError("La fecha de fin no puede ser None")

        # 2. Normalizar datetime a date si es necesario
        normalized_start = self._normalize_date(self.start_date, "start_date")
        normalized_end = self._normalize_date(self.end_date, "end_date")

        # 3. Validar que start_date <= end_date
        if normalized_start > normalized_end:
            raise InvalidDateRangeError(
                f"La fecha de inicio ({normalized_start}) debe ser menor o igual "
                f"que la fecha de fin ({normalized_end})"
            )

        # 4. Asignar valores normalizados (usar object.__setattr__ porque es frozen)
        object.__setattr__(self, 'start_date', normalized_start)
        object.__setattr__(self, 'end_date', normalized_end)

    def _normalize_date(self, value: Union[date, datetime], field_name: str) -> date:
        """
        Normaliza un valor a tipo date.

        Args:
            value: El valor a normalizar (date o datetime)
            field_name: Nombre del campo (para mensajes de error)

        Returns:
            date: La fecha normalizada

        Raises:
            InvalidDateRangeError: Si el tipo no es válido
        """
        if isinstance(value, datetime):
            return value.date()
        elif isinstance(value, date):
            return value
        else:
            raise InvalidDateRangeError(
                f"{field_name} debe ser de tipo date o datetime, "
                f"se recibió {type(value).__name__}"
            )

    def duration_days(self) -> int:
        """
        Calcula la duración del rango en días.

        Returns:
            int: Número de días entre start_date y end_date (inclusive)

        Ejemplos:
            >>> range1 = DateRange(date(2025, 6, 1), date(2025, 6, 3))
            >>> range1.duration_days()
            2  # De 1 a 3 son 2 días de diferencia
        """
        delta = self.end_date - self.start_date
        return delta.days

    def includes(self, check_date: date) -> bool:
        """
        Verifica si una fecha está dentro del rango (inclusive).

        Args:
            check_date: Fecha a verificar

        Returns:
            bool: True si la fecha está en el rango, False en caso contrario

        Ejemplos:
            >>> range1 = DateRange(date(2025, 6, 1), date(2025, 6, 3))
            >>> range1.includes(date(2025, 6, 2))
            True
            >>> range1.includes(date(2025, 6, 5))
            False
        """
        return self.start_date <= check_date <= self.end_date

    def overlaps_with(self, other: 'DateRange') -> bool:
        """
        Verifica si este rango se solapa con otro.

        Args:
            other: Otro DateRange a comparar

        Returns:
            bool: True si hay solapamiento, False en caso contrario

        Ejemplos:
            >>> range1 = DateRange(date(2025, 6, 1), date(2025, 6, 3))
            >>> range2 = DateRange(date(2025, 6, 2), date(2025, 6, 4))
            >>> range1.overlaps_with(range2)
            True
        """
        return (
            self.start_date <= other.end_date and
            self.end_date >= other.start_date
        )

    def __str__(self) -> str:
        """Representación string legible."""
        return f"{self.start_date} to {self.end_date}"

    def __eq__(self, other) -> bool:
        """
        Operador de igualdad - Comparación por valor.

        Dos DateRange son iguales si tienen las mismas fechas.
        """
        return (
            isinstance(other, DateRange) and
            self.start_date == other.start_date and
            self.end_date == other.end_date
        )

    def __hash__(self) -> int:
        """Hash del objeto - Permite usar en sets y como keys de dict."""
        return hash((self.start_date, self.end_date))

    def __composite_values__(self):
        """
        Retorna los valores para SQLAlchemy composite mapping.

        Requerido para que SQLAlchemy pueda persistir el Value Object.
        """
        return (self.start_date, self.end_date)
