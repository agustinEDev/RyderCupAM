"""
Password Value Object - Password seguro con hashing y validación.

Este Value Object representa un password hasheado y validado.

Password Policy (OWASP ASVS compliant):
- Mínimo 12 caracteres (antes 8, actualizado según OWASP 2024)
- Máximo 128 caracteres
- Al menos 1 mayúscula
- Al menos 1 minúscula
- Al menos 1 número
- Al menos 1 carácter especial (!@#$%^&*()_+-=[]{}|;:,.<>?)
- No estar en blacklist de contraseñas comunes (top 100)
- Sin espacios al inicio/final

OWASP Coverage:
- A07: Identification and Authentication Failures
"""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

import bcrypt

from src.shared.security.password_blacklist import is_common_password


class CodigoDeContrasena(StrEnum):
    """El código de cada regla, estable para el cliente (BE #519)."""

    EMPTY = "PASSWORD_EMPTY"
    EDGE_SPACES = "PASSWORD_EDGE_SPACES"
    TOO_SHORT = "PASSWORD_TOO_SHORT"
    TOO_LONG = "PASSWORD_TOO_LONG"
    NO_UPPERCASE = "PASSWORD_NO_UPPERCASE"
    NO_LOWERCASE = "PASSWORD_NO_LOWERCASE"
    NO_DIGIT = "PASSWORD_NO_DIGIT"
    NO_SYMBOL = "PASSWORD_NO_SYMBOL"
    TOO_COMMON = "PASSWORD_TOO_COMMON"
    REUSED = "PASSWORD_REUSED"
    INVALID = "PASSWORD_INVALID"


class InvalidPasswordError(ValueError):
    """
    Excepción lanzada cuando un password no es válido.

    Es un `ValueError` porque los endpoints que reciben una contraseña nueva
    (registro, reset y cambio desde el perfil) convierten ese tipo en un 400 con
    el motivo. Siendo una `Exception` a secas se escapaba como un 500 y el
    usuario leía «Error interno del servidor» en vez de qué le falta.
    """

    def __init__(self, message: str, error_code: str = CodigoDeContrasena.INVALID):
        super().__init__(message)
        # Una regla, un código (BE #519): el mensaje va en español, y el cliente
        # necesita algo estable para enseñarlo en el idioma del usuario. Con el
        # nombre de siempre en el proyecto (`error_code`, como SCORING_NOT_OPEN_YET)
        self.error_code = error_code


def _rota(codigo: CodigoDeContrasena, detalle: str = "") -> tuple[CodigoDeContrasena, str]:
    """La regla rota: su código y su texto, con lo tecleado si hace falta."""
    return codigo, f"{MENSAJES_DE_LA_CONTRASENA[codigo]}{detalle}"


@dataclass(frozen=True)
class Password:
    """
    Value Object para passwords hasheados.

    Almacena el hash, no el password original.

    Password Policy Enforcement (OWASP ASVS V2.1):
    - Longitud: 12-128 caracteres
    - Complejidad: mayúscula + minúscula + número + símbolo
    - Blacklist: Rechaza top 100 contraseñas comunes
    - Sin espacios leading/trailing
    """

    MIN_LENGTH = 12  # OWASP recomienda 12+ desde 2024 (antes era 8)
    MAX_LENGTH = 128  # Límite técnico razonable
    # bcrypt solo usa los primeros 72 BYTES. bcrypt 4 recortaba el resto en silencio;
    # bcrypt 5 lanza ValueError. Se recorta aquí, igual que hacía bcrypt 4, para que
    # los hashes guardados sigan valiendo. Una contraseña de 128 caracteres, o de
    # menos con eñes o acentos (2 bytes cada uno), pasa de 72 bytes.
    BCRYPT_MAX_BYTES = 72
    hashed_value: str

    @classmethod
    def from_plain_text(cls, plain_password: str) -> "Password":
        """
        Crea Password desde texto plano.
        Valida fortaleza según OWASP ASVS y hashea automáticamente.

        Args:
            plain_password: Contraseña en texto plano a validar y hashear

        Returns:
            Password: Value Object con el hash bcrypt

        Raises:
            InvalidPasswordError: Si la contraseña no cumple los requisitos de seguridad
                                  El mensaje indica exactamente qué falta

        Examples:
            >>> pwd = Password.from_plain_text("MySecureP@ssw0rd2025")
            >>> pwd.verify("MySecureP@ssw0rd2025")
            True
        """
        # Validar fortaleza ANTES de hashear
        violation = cls._password_violation(plain_password)
        if violation:
            code, error_message = violation
            raise InvalidPasswordError(error_message, error_code=code)

        hashed = cls._hash_password(plain_password)
        return cls(hashed)

    @classmethod
    def _bcrypt_bytes(cls, plain_password: str) -> bytes:
        """Los bytes que ve bcrypt: la contraseña en UTF-8, recortada a 72 bytes."""
        return plain_password.encode("utf-8")[: cls.BCRYPT_MAX_BYTES]

    @staticmethod
    def _hash_password(plain_password: str) -> str:
        """Hashea password con bcrypt y salt."""
        # Usar rounds mínimo de bcrypt para tests (4 es el mínimo permitido)
        # 4 rounds en tests: ~5ms por hash (ya optimizado vs 12 rounds)
        # 12 rounds en producción: ~200ms por hash (seguro según OWASP)
        rounds = 4 if os.getenv("TESTING") == "true" else 12
        salt = bcrypt.gensalt(rounds=rounds)
        hashed = bcrypt.hashpw(Password._bcrypt_bytes(plain_password), salt)
        return hashed.decode("utf-8")

    @classmethod
    def _validate_password_strength(cls, password: str) -> str | None:
        """El mensaje de la primera regla que se rompe, o None si la contraseña vale."""
        violation = cls._password_violation(password)
        return violation[1] if violation else None

    @staticmethod
    def _password_violation(password: str) -> tuple[CodigoDeContrasena, str] | None:  # noqa: PLR0911
        """
        Valida la fortaleza de la contraseña según OWASP ASVS V2.1.

        Args:
            password: Contraseña en texto plano a validar

        Returns:
            None si la contraseña es válida; si no, (código, mensaje) de la
            primera regla que rompe. El código es estable para el cliente (BE #519)

        OWASP ASVS V2.1 Requirements:
        - V2.1.1: Longitud mínima 12 caracteres (antes 8)
        - V2.1.2: Máximo 128 caracteres
        - V2.1.6: Complejidad (mayús + minús + número + símbolo)
        - V2.1.7: Blacklist de contraseñas comunes
        """
        # 1. Validar que la contraseña no sea None o vacía
        if not password:
            return _rota(CodigoDeContrasena.EMPTY)

        # 2. Remover espacios leading/trailing (común en copy-paste)
        password_trimmed = password.strip()
        if password_trimmed != password:
            return _rota(CodigoDeContrasena.EDGE_SPACES)

        # 3. Validar longitud mínima (OWASP: 12+ chars)
        if len(password) < Password.MIN_LENGTH:
            return _rota(CodigoDeContrasena.TOO_SHORT, f" (actualmente: {len(password)})")

        # 4. Validar longitud máxima (límite técnico)
        if len(password) > Password.MAX_LENGTH:
            return _rota(CodigoDeContrasena.TOO_LONG, f" (actualmente: {len(password)})")

        # 5. Validar complejidad: al menos 1 mayúscula
        if not any(c.isupper() for c in password):
            return _rota(CodigoDeContrasena.NO_UPPERCASE)

        # 6. Validar complejidad: al menos 1 minúscula
        if not any(c.islower() for c in password):
            return _rota(CodigoDeContrasena.NO_LOWERCASE)

        # 7. Validar complejidad: al menos 1 número
        if not any(c.isdigit() for c in password):
            return _rota(CodigoDeContrasena.NO_DIGIT)

        # 8. Validar complejidad: al menos 1 carácter especial
        # Caracteres especiales permitidos: !@#$%^&*()_+-=[]{}|;:,.<>?
        special_chars_pattern = r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]"
        if not re.search(special_chars_pattern, password):
            return _rota(CodigoDeContrasena.NO_SYMBOL)

        # 9. Validar contra blacklist de contraseñas comunes (OWASP V2.1.7)
        if is_common_password(password):
            return _rota(CodigoDeContrasena.TOO_COMMON)

        # Todas las validaciones pasaron
        return None

    @staticmethod
    def _is_strong_password(password: str) -> bool:
        """
        Método legacy para backward compatibility.
        Usa el nuevo _validate_password_strength internamente.

        DEPRECATED: Usar _validate_password_strength para mensajes de error detallados.
        """
        return Password._validate_password_strength(password) is None

    def verify(self, plain_password: str) -> bool:
        """Verifica si un password plano coincide con el hash."""
        try:
            return bcrypt.checkpw(
                self._bcrypt_bytes(plain_password), self.hashed_value.encode("utf-8")
            )
        except Exception:
            return False

    def __str__(self) -> str:
        """Representación string segura (sin mostrar hash)."""
        return "[Password Hash]"

    def __eq__(self, other) -> bool:
        """Operador de igualdad."""
        return isinstance(other, Password) and self.hashed_value == other.hashed_value

    def __hash__(self) -> int:
        """Hash del objeto - Permite usar en sets y como keys de dict."""
        return hash(self.hashed_value)


# El texto de cada código, uno solo: lo dicen el dominio y la ruta, que no copia
# nada (BE #562). La longitud, sin lo tecleado: el dominio le añade
# «(actualmente: N)». REUSED va en inglés: el cliente lo buscaba por ese texto.
MENSAJES_DE_LA_CONTRASENA: Mapping[str, str] = MappingProxyType(
    {
        CodigoDeContrasena.EMPTY: "La contraseña no puede estar vacía",
        CodigoDeContrasena.EDGE_SPACES: "La contraseña no puede tener espacios al inicio o final",
        CodigoDeContrasena.TOO_SHORT: f"La contraseña debe tener al menos {Password.MIN_LENGTH} caracteres",
        CodigoDeContrasena.TOO_LONG: f"La contraseña no puede exceder {Password.MAX_LENGTH} caracteres",
        CodigoDeContrasena.NO_UPPERCASE: "La contraseña debe contener al menos una letra mayúscula (A-Z)",
        CodigoDeContrasena.NO_LOWERCASE: "La contraseña debe contener al menos una letra minúscula (a-z)",
        CodigoDeContrasena.NO_DIGIT: "La contraseña debe contener al menos un número (0-9)",
        CodigoDeContrasena.NO_SYMBOL: (
            "La contraseña debe contener al menos un carácter especial (!@#$%^&*()_+-=[]{}|;:,.<>?)"
        ),
        CodigoDeContrasena.TOO_COMMON: (
            "Esta contraseña es demasiado común y fácil de adivinar. Por favor, elige una "
            "contraseña más única"
        ),
        CodigoDeContrasena.REUSED: (
            "Cannot reuse any of your last 5 passwords. Please choose a different password."
        ),
        CodigoDeContrasena.INVALID: "La contraseña no es válida",
    }
)
