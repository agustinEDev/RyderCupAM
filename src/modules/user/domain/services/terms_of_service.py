"""
La versión vigente de los Términos de uso.

Es una constante del backend y no una tabla: una versión nueva sale con una
release, igual que el texto de los Términos que publica el frontend.

CAMBIARLA OBLIGA A TODOS A ACEPTAR DE NUEVO. Quien tenga aceptada otra versión
recibe un 403 `TERMS_NOT_ACCEPTED` en cualquier ruta con sesión (salvo las
exentas de `src/config/dependencies.py`) hasta que acepte la nueva con
`POST /api/v1/users/me/accept-terms`. Se cambia a la vez que el texto, en la
misma release que el frontend.

Formato: la fecha de publicación del texto, `AAAA-MM-DD`.
"""

# Largo de la columna `users.terms_version`
TERMS_VERSION_MAX_LENGTH = 20

CURRENT_TERMS_VERSION = "2026-10-20"


def current_terms_version() -> str:
    """
    La versión que hay que tener aceptada para usar la aplicación.

    Se lee la constante en cada llamada (no una copia de cuando se importó),
    para que haya un único sitio que cambiar y los tests puedan simular una
    versión nueva.
    """
    return CURRENT_TERMS_VERSION
