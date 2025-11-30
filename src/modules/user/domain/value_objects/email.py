"""
Email Value Object - Dirección de email válida y normalizada.

Este Value Object representa una dirección de email.
"""

from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email


class InvalidEmailError(Exception):
    """Excepción lanzada cuando un email no es válido."""
    pass


@dataclass(frozen=True)
class Email:
    """
    Value Object para direcciones de email.

    Inmutable y validado automáticamente.
    """

    value: str

    def __post_init__(self):
        """Validación y normalización automática."""
        if not isinstance(self.value, str):
            raise InvalidEmailError("El email debe ser un string")

        # 1. Normalizar: quitar espacios y convertir a minúsculas ANTES de validar
        normalized_email = self.value.strip().lower()

        if not normalized_email:
            raise InvalidEmailError("El email no puede ser nulo o vacío")

        try:
            # 2. Validar el email ya normalizado
            valid = validate_email(normalized_email, check_deliverability=False)

            # 3. Asignar el valor normalizado y validado
            # Usar object.__setattr__ porque la clase es frozen
            object.__setattr__(self, 'value', valid.normalized)

        except EmailNotValidError as e:
            # Capturar el error de la librería y lanzar nuestra excepción de dominio
            raise InvalidEmailError(f"'{self.value}' no es un email válido: {e}") from e



    def __str__(self) -> str:
        """Representación string legible."""
        return self.value

    def __eq__(self, other) -> bool:
        """Operador de igualdad."""
        return isinstance(other, Email) and self.value == other.value

    def __hash__(self) -> int:
        """Hash del objeto - Permite usar en sets y como keys de dict."""
        return hash(self.value)
