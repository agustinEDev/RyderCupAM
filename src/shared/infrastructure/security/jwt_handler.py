"""
JWT Token Handler

Utilidades para crear y verificar tokens JWT (JSON Web Tokens).
Implementa autenticación basada en tokens con algoritmo HS256.
"""

from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt

from src.config.settings import settings
from src.modules.user.application.ports.token_service_interface import ITokenService


class JWTTokenService(ITokenService):
    """
    Implementación de ITokenService usando JWT (JSON Web Tokens).

    Esta es una implementación concreta del puerto ITokenService usando
    la librería python-jose con algoritmo HS256.

    Puede ser reemplazada por otras implementaciones (OAuth2, Paseto, etc.)
    sin afectar a la capa de aplicación.
    """

    def create_access_token(
        self,
        data: dict,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Crea un token JWT de acceso.

        Args:
            data: Datos a incluir en el payload del token (ej: {"sub": user_id})
            expires_delta: Tiempo de expiración personalizado. Si None, usa el default de settings.

        Returns:
            Token JWT codificado como string
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now() + expires_delta
        else:
            expire = datetime.now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire})

        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

        return encoded_jwt

    def verify_access_token(self, token: str) -> Optional[dict]:
        """
        Verifica y decodifica un token JWT.

        Args:
            token: Token JWT a verificar

        Returns:
            Payload del token si es válido, None si es inválido o expirado
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            return payload
        except JWTError:
            return None


# ============================================================================
# FUNCIONES DE COMPATIBILIDAD (deprecadas, usar JWTTokenService en su lugar)
# ============================================================================


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Crea un token JWT de acceso.

    Args:
        data: Datos a incluir en el payload del token (ej: {"sub": user_id})
        expires_delta: Tiempo de expiración personalizado. Si None, usa el default de settings.

    Returns:
        Token JWT codificado como string

    Example:
        >>> token = create_access_token({"sub": "user-123"})
        >>> # Token válido por ACCESS_TOKEN_EXPIRE_MINUTES
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encoded_jwt


def verify_access_token(token: str) -> Optional[dict]:
    """
    Verifica y decodifica un token JWT.

    Args:
        token: Token JWT a verificar

    Returns:
        Payload del token si es válido, None si es inválido o expirado

    Example:
        >>> payload = verify_access_token(token)
        >>> if payload:
        >>>     user_id = payload.get("sub")
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None
