"""
Módulo de Validación Compartido (v1.8.0)

Este módulo proporciona utilidades de validación y sanitización
para asegurar que los datos de entrada sean seguros y consistentes.

OWASP Coverage:
- A03: Injection (sanitización HTML, validación estricta)
- A04: Insecure Design (límites de longitud, prevención DoS)
"""

from .field_limits import FieldLimits
from .sanitizers import sanitize_html
from .validators import AliasValidator, NameValidator

__all__ = [
    "AliasValidator",
    "FieldLimits",
    "NameValidator",
    "sanitize_html",
]
