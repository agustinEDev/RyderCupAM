"""
La versión vigente de los Términos de uso.

Es una constante del backend y no una tabla: una versión nueva sale con una
release, igual que el texto de los Términos que publica el frontend.

CAMBIARLA OBLIGA A TODOS A ACEPTAR DE NUEVO. Quien tenga aceptada otra versión
recibe un 403 `TERMS_NOT_ACCEPTED` en cualquier ruta con sesión (salvo las
exentas de `src/config/terms_guard.py`) hasta que acepte la nueva con
`POST /api/v1/users/me/accept-terms`. Se cambia a la vez que el texto, en la
misma release que el frontend.

Formato: la fecha de publicación del texto, `AAAA-MM-DD`.
"""

from datetime import datetime, timedelta

# Largo de la columna `users.terms_version`
TERMS_VERSION_MAX_LENGTH = 20

CURRENT_TERMS_VERSION = "2026-10-20"


def validate_terms_version(version: str) -> str:
    """
    Una versión de los Términos válida: no vacía y que quepa en su columna.

    Raises:
        ValueError: Si está vacía, en blanco o es más larga que TERMS_VERSION_MAX_LENGTH
    """
    if not version.strip() or len(version) > TERMS_VERSION_MAX_LENGTH:
        raise ValueError(f"Versión de los Términos no válida: {version!r}")
    return version


def require_utc(value: datetime, name: str) -> datetime:
    """
    La misma fecha, si va en UTC con zona horaria.

    Sin zona, `utcoffset()` es None y también se rechaza: en el historial de
    los Términos todo va en UTC.

    Args:
        value: La fecha
        name: El nombre del campo, para el mensaje

    Raises:
        ValueError: Si no lleva zona o no es UTC
    """
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} debe ir en UTC, con zona horaria")
    return value


def current_terms_version() -> str:
    """
    La versión que hay que tener aceptada para usar la aplicación.

    Se lee la constante en cada llamada (no una copia de cuando se importó),
    para que haya un único sitio que cambiar y los tests puedan simular una
    versión nueva.
    """
    return CURRENT_TERMS_VERSION


# Conservación del historial de aceptaciones tras el BORRADO de la cuenta
# (decisión de Agustín, 20 oct 2026): la fila sobrevive al usuario, como
# prueba de que aceptó, durante este número de años naturales contados desde
# el borrado, y después la purga la elimina (scripts/purge_terms_acceptances.py).
# Mientras la cuenta existe, el historial se conserva entero.
TERMS_ACCEPTANCE_RETENTION_YEARS = 3


def terms_acceptance_purge_cutoff(now: datetime) -> datetime:
    """
    Antes de este instante, una cuenta borrada ya cumplió su plazo de conservación.

    Son TERMS_ACCEPTANCE_RETENTION_YEARS años naturales antes de `now`; un 29
    de febrero cae en el 28 si el año de destino no es bisiesto.

    Args:
        now: Ahora, en UTC

    Raises:
        ValueError: Si `now` no va en UTC
    """
    require_utc(now, "now")
    year = now.year - TERMS_ACCEPTANCE_RETENTION_YEARS
    try:
        return now.replace(year=year)
    except ValueError:
        return now.replace(year=year, day=28)
