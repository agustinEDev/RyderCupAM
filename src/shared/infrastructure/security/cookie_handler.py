"""
Cookie Handler para Autenticación con httpOnly Cookies.

Este módulo centraliza la configuración de cookies de autenticación seguras
para proteger contra ataques XSS (Cross-Site Scripting).

OWASP A01: Broken Access Control
OWASP A02: Cryptographic Failures

Arquitectura:
- Capa: Infrastructure (Shared)
- Responsabilidad: Gestión de cookies HTTP seguras
- Patrón: Helper/Utility
"""
import os
from typing import Optional

from fastapi import Response


# Nombres de las cookies
COOKIE_NAME = "access_token"          # Access token (15 min)
REFRESH_COOKIE_NAME = "refresh_token"  # Refresh token (7 días)

# Tiempos de expiración (deben coincidir con la expiración de los JWT)
COOKIE_MAX_AGE = 900           # 15 minutos (access token reducido desde 1 hora)
REFRESH_COOKIE_MAX_AGE = 604800  # 7 días en segundos (refresh token)


def is_production() -> bool:
    """
    Detecta si la aplicación está corriendo en producción.

    Returns:
        True si ENVIRONMENT=production, False en caso contrario
    """
    return os.getenv("ENVIRONMENT", "development").lower() == "production"


def set_auth_cookie(response: Response, token: str) -> None:
    """
    Establece una cookie httpOnly con el JWT de autenticación.

    Esta función configura una cookie segura con los siguientes parámetros:

    Parámetros de Seguridad:
    - httponly=True: Previene acceso desde JavaScript (protección XSS)
    - secure=True/False: Solo HTTPS en producción, HTTP permitido en desarrollo
    - samesite="lax": Protección contra CSRF, permite navegación normal
    - max_age=3600: Expira en 1 hora (igual que el JWT)
    - path="/": Cookie disponible en toda la aplicación

    Args:
        response: Objeto Response de FastAPI donde se añadirá la cookie
        token: JWT token a almacenar en la cookie

    Example:
        >>> from fastapi import Response
        >>> response = Response()
        >>> set_auth_cookie(response, "eyJhbGciOiJIUzI1...")
        >>> # Cookie añadida a response.headers["Set-Cookie"]

    Security Notes:
        - httponly=True: JavaScript NO puede leer la cookie (previene XSS)
        - secure=True (producción): Cookie solo se envía por HTTPS
        - secure=False (desarrollo): Permite HTTP en localhost
        - samesite="lax": Balancea seguridad y usabilidad
          * Previene CSRF en la mayoría de casos
          * Permite navegación normal (GET requests desde enlaces)
          * Para máxima seguridad usar "strict" (puede afectar UX)

    OWASP Compliance:
        - A01: Broken Access Control → httpOnly previene robo de tokens
        - A02: Cryptographic Failures → secure=True fuerza cifrado HTTPS
        - A07: Authentication Failures → Configuración segura de sesión
    """
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,              # ✅ Protección XSS: No accesible desde JavaScript
        secure=is_production(),      # ✅ HTTPS en producción, HTTP en desarrollo
        samesite="lax",             # ✅ Protección CSRF moderada
        max_age=COOKIE_MAX_AGE,     # ✅ Expira en 1 hora
        path="/",                    # ✅ Disponible en toda la app
    )


def delete_auth_cookie(response: Response) -> None:
    """
    Elimina la cookie de autenticación (logout).

    Esta función invalida la cookie estableciendo su valor vacío y
    expiración en 0 (eliminación inmediata).

    Args:
        response: Objeto Response de FastAPI donde se eliminará la cookie

    Example:
        >>> from fastapi import Response
        >>> response = Response()
        >>> delete_auth_cookie(response)
        >>> # Cookie eliminada del navegador

    Note:
        Esta función solo elimina la cookie del lado del cliente.
        El token JWT en sí sigue siendo técnicamente válido hasta su expiración.
        Para invalidación completa, se requeriría una blacklist de tokens (Fase 2).
    """
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",                    # Mismo path que al crear la cookie
        httponly=True,              # Mismo httponly que al crear
        secure=is_production(),      # Mismo secure que al crear
        samesite="lax",             # Mismo samesite que al crear
    )


def get_cookie_name() -> str:
    """
    Retorna el nombre de la cookie de autenticación.

    Útil para extraer el token desde las cookies en el middleware.

    Returns:
        Nombre de la cookie (constante COOKIE_NAME)

    Example:
        >>> get_cookie_name()
        'access_token'
    """
    return COOKIE_NAME


# =============================================================================
# Refresh Token Cookie Handlers (Session Timeout - v1.8.0)
# =============================================================================


def set_refresh_token_cookie(response: Response, refresh_token: str) -> None:
    """
    Establece una cookie httpOnly con el refresh token JWT.

    El refresh token tiene mayor duración (7 días) y se usa exclusivamente
    para renovar access tokens, no para acceder a recursos.

    Parámetros de Seguridad:
    - httponly=True: Previene acceso desde JavaScript (protección XSS)
    - secure=True/False: Solo HTTPS en producción, HTTP permitido en desarrollo
    - samesite="lax": Protección contra CSRF, permite navegación normal
    - max_age=604800: Expira en 7 días (igual que el refresh token JWT)
    - path="/": Cookie disponible en toda la aplicación

    Args:
        response: Objeto Response de FastAPI donde se añadirá la cookie
        refresh_token: Refresh token JWT a almacenar en la cookie

    Example:
        >>> from fastapi import Response
        >>> response = Response()
        >>> set_refresh_token_cookie(response, "eyJhbGciOiJIUzI1...")
        >>> # Cookie refresh_token añadida a response.headers["Set-Cookie"]

    Security Notes:
        - httponly=True: JavaScript NO puede leer la cookie (previene XSS)
        - Mayor duración que access token (7 días vs 15 min)
        - Solo usado en endpoint /refresh-token (no en requests normales)

    OWASP Compliance:
        - A01: Broken Access Control → httpOnly previene robo de tokens
        - A02: Cryptographic Failures → secure=True fuerza cifrado HTTPS
        - A07: Authentication Failures → Session timeout con refresh pattern
    """
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,              # ✅ Protección XSS
        secure=is_production(),      # ✅ HTTPS en producción
        samesite="lax",             # ✅ Protección CSRF
        max_age=REFRESH_COOKIE_MAX_AGE,  # ✅ Expira en 7 días
        path="/",                    # ✅ Disponible en toda la app
    )


def delete_refresh_token_cookie(response: Response) -> None:
    """
    Elimina la cookie de refresh token (logout).

    Esta función invalida la cookie estableciendo su valor vacío y
    expiración en 0 (eliminación inmediata).

    Args:
        response: Objeto Response de FastAPI donde se eliminará la cookie

    Example:
        >>> from fastapi import Response
        >>> response = Response()
        >>> delete_refresh_token_cookie(response)
        >>> # Cookie refresh_token eliminada del navegador

    Note:
        Esta función solo elimina la cookie del lado del cliente.
        El refresh token en BD debe ser revocado por LogoutUserUseCase.
    """
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/",                    # Mismo path que al crear la cookie
        httponly=True,              # Mismo httponly que al crear
        secure=is_production(),      # Mismo secure que al crear
        samesite="lax",             # Mismo samesite que al crear
    )


def get_refresh_cookie_name() -> str:
    """
    Retorna el nombre de la cookie de refresh token.

    Útil para extraer el refresh token desde las cookies en endpoints.

    Returns:
        Nombre de la cookie de refresh token (constante REFRESH_COOKIE_NAME)

    Example:
        >>> get_refresh_cookie_name()
        'refresh_token'
    """
    return REFRESH_COOKIE_NAME
