"""
Códigos de error de la cuenta que comparten varias rutas, con su texto fijo: la app
traduce por el código (los textos del backend salían en inglés, probador de la release).
"""

CURRENT_PASSWORD_INCORRECT = "CURRENT_PASSWORD_INCORRECT"  # nosec B105 - an error code, not a password
EMAIL_ALREADY_IN_USE = "EMAIL_ALREADY_IN_USE"

TEXTOS = {
    CURRENT_PASSWORD_INCORRECT: "Current password is incorrect.",
    EMAIL_ALREADY_IN_USE: "That email is already used by another account.",
}
