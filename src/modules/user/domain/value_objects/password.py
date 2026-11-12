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

import contextlib
import functools
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from src.modules.user.domain.ports.password_hasher import hasher_de_contrasenas
from src.modules.user.domain.value_objects.password_blacklist import is_common_password


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
    hashed_value: str
    # Solo la pone from_plain_text: el usuario acepta un Password ya calculado (el
    # bcrypt fuera de la transacción, BE #283) solo si pasó por la política. Fuera del
    # constructor (init=False): ni se puede poner desde fuera ni la ve el mapeo de
    # SQLAlchemy, que saca los valores de la firma del constructor (una sola columna).
    # La igualdad la decide __eq__ (solo el hash)
    de_texto_plano: bool = field(default=False, init=False, repr=False)

    @classmethod
    def comprueba_la_politica(cls, plain_password: str) -> None:
        """La política, sin calcular ningún bcrypt (barata: va antes de cualquier hash).

        Raises:
            InvalidPasswordError: con el código y el texto de la regla rota
        """
        violation = cls._password_violation(plain_password)
        if violation:
            code, error_message = violation
            raise InvalidPasswordError(error_message, error_code=code)

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
        cls.comprueba_la_politica(plain_password)

        hashed = cls._hash_password(plain_password)
        contrasena = cls(hashed)
        object.__setattr__(contrasena, "de_texto_plano", True)
        return contrasena

    @staticmethod
    def _hash_password(plain_password: str) -> str:
        """El hash, con el hasher que instala la composition root (bcrypt, 12 rondas)."""
        return hasher_de_contrasenas().hash(plain_password)

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
    @functools.cache
    def _relleno() -> str:
        """
        Un hash de una contraseña al azar que nadie conoce, calculado UNA vez por
        proceso y con el mismo coste que los reales (`_hash_password`).
        """
        return Password._hash_password(secrets.token_urlsafe(32))

    @classmethod
    def verifica_contra_el_relleno(cls, plain_password: str) -> bool:
        """
        Paga el mismo bcrypt que una contraseña de verdad y dice siempre que no
        (BE #281).

        Para el login con un email que no existe: sin esto respondía ~500 ms
        antes que con una cuenta real, y el cronómetro decía quién está
        registrado (OWASP A07). El resultado del hash se descarta: el «no» no
        depende de que el azar no acierte.
        """
        # Mismo trato que `verify` ante un error de bcrypt: no es la respuesta
        relleno = cls._relleno()
        with contextlib.suppress(Exception):
            hasher_de_contrasenas().matches(plain_password, relleno)
        return False

    def verify(self, plain_password: str) -> bool:
        """Verifica si un password plano coincide con el hash."""
        hasher = hasher_de_contrasenas()
        try:
            return hasher.matches(plain_password, self.hashed_value)
        except Exception:
            return False

    def __str__(self) -> str:
        """Representación string segura (sin mostrar hash)."""
        return "[Password Hash]"

    def __eq__(self, other: object) -> bool:
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
