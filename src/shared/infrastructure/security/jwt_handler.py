"""
JWT Token Handler

Utilidades para crear y verificar tokens JWT (JSON Web Tokens).
Implementa autenticación basada en tokens con algoritmo HS256.
"""

import uuid
from datetime import datetime, timedelta

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

    Session Timeout (v1.8.0):
    - Access Token: 15 minutos (operaciones frecuentes)
    - Refresh Token: 7 días (renovación sin re-login)
    """

    def create_access_token(
        self,
        data: dict,
        expires_delta: timedelta | None = None
    ) -> str:
        """
        Crea un token JWT de acceso (15 minutos por defecto).

        Args:
            data: Datos a incluir en el payload del token (ej: {"sub": user_id})
            expires_delta: Tiempo de expiración personalizado. Si None, usa 15 min.

        Returns:
            Token JWT codificado como string
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now() + expires_delta
        else:
            expire = datetime.now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire, "type": "access"})

        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

        return encoded_jwt

    def create_refresh_token(
        self,
        data: dict,
        expires_delta: timedelta | None = None
    ) -> str:
        """
        Crea un token JWT de renovación (7 días por defecto).

        Los refresh tokens tienen mayor duración y se usan solo para
        obtener nuevos access tokens, no para acceder a recursos.

        Incluye un jti (JWT ID) único para garantizar que cada token sea único,
        incluso si se generan múltiples tokens para el mismo usuario al mismo tiempo.

        Args:
            data: Datos a incluir en el payload (ej: {"sub": user_id})
            expires_delta: Tiempo de expiración personalizado. Si None, usa 7 días.

        Returns:
            Token JWT codificado como string

        Example:
            >>> service = JWTTokenService()
            >>> refresh_token = service.create_refresh_token({"sub": "user-123"})
            >>> # Token válido por 7 días con jti único
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now() + expires_delta
        else:
            expire = datetime.now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        # Agregar jti (JWT ID) único para garantizar unicidad del token
        # Esto previene colisiones de hash cuando se generan múltiples tokens al mismo tiempo
        to_encode.update({
            "exp": expire,
            "type": "refresh",
            "jti": str(uuid.uuid4())  # JWT ID único por token
        })

        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

        return encoded_jwt

    def verify_access_token(self, token: str) -> dict | None:
        """
        Verifica y decodifica un token JWT de acceso.

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

            # Verificar que sea un access token (v1.8.0+)
            if payload.get("type") == "refresh":
                # No permitir refresh tokens en endpoints de access token
                return None

            return payload
        except JWTError:
            return None

    def verify_refresh_token(self, token: str) -> dict | None:
        """
        Verifica y decodifica un token JWT de renovación.

        Args:
            token: Refresh token JWT a verificar

        Returns:
            Payload del token si es válido, None si es inválido o expirado

        Example:
            >>> service = JWTTokenService()
            >>> payload = service.verify_refresh_token(refresh_token)
            >>> if payload:
            >>>     user_id = payload.get("sub")
            >>>     # Generar nuevo access token
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )

            # Verificar que sea un refresh token
            if payload.get("type") != "refresh":
                return None

            return payload
        except JWTError:
            return None


# ============================================================================
# FUNCIONES DE COMPATIBILIDAD (deprecadas, usar JWTTokenService en su lugar)
# ============================================================================


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Crea un token JWT de acceso (15 minutos).

    DEPRECATED: Usar JWTTokenService().create_access_token() en su lugar.

    Args:
        data: Datos a incluir en el payload del token (ej: {"sub": user_id})
        expires_delta: Tiempo de expiración personalizado. Si None, usa 15 min.

    Returns:
        Token JWT codificado como string

    Example:
        >>> token = create_access_token({"sub": "user-123"})
        >>> # Token válido por 15 minutos
    """
    service = JWTTokenService()
    return service.create_access_token(data, expires_delta)


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Crea un token JWT de renovación (7 días).

    DEPRECATED: Usar JWTTokenService().create_refresh_token() en su lugar.

    Args:
        data: Datos a incluir en el payload (ej: {"sub": user_id})
        expires_delta: Tiempo de expiración personalizado. Si None, usa 7 días.

    Returns:
        Token JWT codificado como string

    Example:
        >>> token = create_refresh_token({"sub": "user-123"})
        >>> # Token válido por 7 días
    """
    service = JWTTokenService()
    return service.create_refresh_token(data, expires_delta)


def verify_access_token(token: str) -> dict | None:
    """
    Verifica y decodifica un token JWT de acceso.

    DEPRECATED: Usar JWTTokenService().verify_access_token() en su lugar.

    Args:
        token: Token JWT a verificar

    Returns:
        Payload del token si es válido, None si es inválido o expirado

    Example:
        >>> payload = verify_access_token(token)
        >>> if payload:
        >>>     user_id = payload.get("sub")
    """
    service = JWTTokenService()
    return service.verify_access_token(token)


def verify_refresh_token(token: str) -> dict | None:
    """
    Verifica y decodifica un token JWT de renovación.

    DEPRECATED: Usar JWTTokenService().verify_refresh_token() en su lugar.

    Args:
        token: Refresh token JWT a verificar

    Returns:
        Payload del token si es válido, None si es inválido o expirado

    Example:
        >>> payload = verify_refresh_token(token)
        >>> if payload:
        >>>     user_id = payload.get("sub")
    """
    service = JWTTokenService()
    return service.verify_refresh_token(token)
