"""
CORS Configuration for Ryder Cup Manager API

Este módulo centraliza la configuración de CORS (Cross-Origin Resource Sharing)
para proteger el backend contra accesos no autorizados desde orígenes externos.

OWASP Coverage:
- A05: Security Misconfiguration (whitelist estricta de orígenes)
- A01: Broken Access Control (control de acceso a nivel de origen)

Features implementadas:
- Whitelist estricta de orígenes (no se permite '*')
- Separación clara entre desarrollo y producción
- Validación de orígenes en tiempo de ejecución
- Soporte para múltiples frontends (web, mobile, etc.)
- allow_credentials=True para cookies httpOnly
"""

import os
from typing import List
from urllib.parse import urlparse


def _is_production() -> bool:
    """
    Determina si la aplicación está corriendo en producción.

    Returns:
        bool: True si ENVIRONMENT=production, False en caso contrario
    """
    return os.getenv("ENVIRONMENT", "development").lower() == "production"


def _parse_frontend_origins() -> List[str]:
    """
    Parsea los orígenes del frontend desde la variable de entorno FRONTEND_ORIGINS.

    El formato esperado es una lista separada por comas:
    FRONTEND_ORIGINS=https://app.rydercupfriends.com,https://www.rydercupfriends.com

    Returns:
        List[str]: Lista de orígenes parseados (sin espacios en blanco)
    """
    frontend_origins_raw = os.getenv("FRONTEND_ORIGINS", "")
    return [origin.strip() for origin in frontend_origins_raw.split(",") if origin.strip()]


def _get_development_origins() -> List[str]:
    """
    Retorna lista de orígenes permitidos en desarrollo local.

    Incluye:
    - localhost:3000 (React/Next.js)
    - localhost:5173/5174 (Vite - puerto por defecto y fallback)
    - localhost:8080 (Kubernetes port-forward)
    - Versiones con 127.0.0.1 de todas las anteriores

    Returns:
        List[str]: Lista de orígenes de desarrollo
    """
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]


def _validate_origins(origins: List[str]) -> List[str]:
    """
    Valida y sanitiza una lista de orígenes CORS.

    Validaciones:
    1. Rechaza wildcards ('*') - no permitidos por seguridad
    2. Rechaza orígenes inválidos (sin esquema http/https)
    3. Elimina duplicados conservando orden
    4. Rechaza orígenes vacíos

    Args:
        origins: Lista de orígenes a validar

    Returns:
        List[str]: Lista de orígenes validados

    Raises:
        ValueError: Si se detecta un origen inválido en producción
    """
    validated = []
    seen = set()

    for origin in origins:
        # Rechazar wildcards
        if origin == "*":
            if _is_production():
                raise ValueError(
                    "CORS: No se permite el wildcard '*' en producción. "
                    "Configure FRONTEND_ORIGINS con orígenes específicos."
                )
            else:
                print(f"⚠️  CORS: Wildcard '*' detectado en desarrollo (ignorado)")
                continue

        # Rechazar orígenes vacíos
        if not origin:
            continue

        # Validar esquema HTTP/HTTPS
        try:
            parsed = urlparse(origin)
            if parsed.scheme not in ["http", "https"]:
                if _is_production():
                    raise ValueError(
                        f"CORS: Origen inválido '{origin}'. "
                        f"Solo se permiten esquemas http/https."
                    )
                else:
                    print(f"⚠️  CORS: Origen inválido '{origin}' (ignorado)")
                    continue
        except Exception as e:
            if _is_production():
                raise ValueError(f"CORS: Error parseando origen '{origin}': {e}")
            else:
                print(f"⚠️  CORS: Error parseando origen '{origin}' (ignorado)")
                continue

        # Eliminar duplicados (preservando orden)
        if origin not in seen:
            validated.append(origin)
            seen.add(origin)

    return validated


def get_allowed_origins() -> List[str]:
    """
    Retorna la lista final de orígenes permitidos según el entorno.

    Lógica:
    - Producción: Solo FRONTEND_ORIGINS (variable de entorno)
    - Desarrollo: FRONTEND_ORIGINS + orígenes de desarrollo local

    Si FRONTEND_ORIGINS está vacío:
    - Producción: Lanza error (configuración requerida)
    - Desarrollo: Usa solo orígenes de desarrollo local

    Returns:
        List[str]: Lista de orígenes permitidos (validada)

    Raises:
        ValueError: Si FRONTEND_ORIGINS está vacío en producción

    Examples:
        # Desarrollo (sin FRONTEND_ORIGINS)
        >>> os.environ['ENVIRONMENT'] = 'development'
        >>> os.environ['FRONTEND_ORIGINS'] = ''
        >>> get_allowed_origins()
        ['http://localhost:3000', 'http://127.0.0.1:3000', ...]

        # Producción
        >>> os.environ['ENVIRONMENT'] = 'production'
        >>> os.environ['FRONTEND_ORIGINS'] = 'https://app.rydercupfriends.com'
        >>> get_allowed_origins()
        ['https://app.rydercupfriends.com']
    """
    is_prod = _is_production()
    frontend_origins = _parse_frontend_origins()

    # En producción, FRONTEND_ORIGINS es obligatorio
    if is_prod and not frontend_origins:
        raise ValueError(
            "CORS: FRONTEND_ORIGINS no está configurado en producción. "
            "Configure la variable de entorno con los orígenes permitidos "
            "(ej: FRONTEND_ORIGINS=https://app.rydercupfriends.com)"
        )

    # Combinar orígenes según entorno
    if is_prod:
        allowed_origins = frontend_origins
    else:
        # En desarrollo, combinar frontend + locales
        dev_origins = _get_development_origins()
        allowed_origins = frontend_origins + dev_origins

    # Validar y sanitizar
    validated_origins = _validate_origins(allowed_origins)

    # Fallback de seguridad en desarrollo (si todo falla)
    if not validated_origins and not is_prod:
        print("⚠️  CORS: Usando fallback de desarrollo (solo localhost)")
        validated_origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

    # En producción, si no hay orígenes válidos, lanzar error
    if not validated_origins and is_prod:
        raise ValueError(
            "CORS: No hay orígenes válidos configurados en producción. "
            "Verifique la configuración de FRONTEND_ORIGINS."
        )

    return validated_origins


def get_cors_config() -> dict:
    """
    Retorna la configuración completa de CORS para FastAPI CORSMiddleware.

    Returns:
        dict: Diccionario con parámetros para CORSMiddleware

    Example:
        >>> from fastapi.middleware.cors import CORSMiddleware
        >>> from src.config.cors_config import get_cors_config
        >>> app.add_middleware(CORSMiddleware, **get_cors_config())
    """
    allowed_origins = get_allowed_origins()

    # Debug log (solo en desarrollo)
    if not _is_production():
        print(f"🔒 CORS allowed_origins ({len(allowed_origins)}):")
        for origin in allowed_origins:
            print(f"   - {origin}")

    return {
        "allow_origins": allowed_origins,
        "allow_credentials": True,  # Requerido para cookies httpOnly (v1.8.0)
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["*"],  # Permitir todos los headers (Content-Type, Authorization, etc.)
        "max_age": 3600,  # Cache de preflight requests (1 hora)
    }


# Variables exportadas para uso en main.py
__all__ = ["get_cors_config", "get_allowed_origins"]
