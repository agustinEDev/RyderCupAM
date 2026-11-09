"""Adaptador de bcrypt para el puerto PasswordHasher (auditoría del 9 nov 2026, B2)."""

import bcrypt

# bcrypt solo usa los primeros 72 BYTES. bcrypt 4 recortaba el resto en silencio;
# bcrypt 5 lanza ValueError. Se recorta aquí, igual que hacía bcrypt 4, para que
# los hashes guardados sigan valiendo. Una contraseña de 128 caracteres, o de
# menos con eñes o acentos (2 bytes cada uno), pasa de 72 bytes.
BCRYPT_MAX_BYTES = 72

# El rango que acepta bcrypt
_RONDAS_MINIMAS = 4
_RONDAS_MAXIMAS = 31


def _bytes(plain: str) -> bytes:
    """Los bytes que ve bcrypt: la contraseña en UTF-8, recortada a 72 bytes."""
    return plain.encode("utf-8")[:BCRYPT_MAX_BYTES]


class BcryptPasswordHasher:
    """Hashes bcrypt con un coste fijo (12 en producción)."""

    def __init__(self, rounds: int) -> None:
        if not _RONDAS_MINIMAS <= rounds <= _RONDAS_MAXIMAS:
            raise ValueError(
                f"bcrypt acepta de {_RONDAS_MINIMAS} a {_RONDAS_MAXIMAS} rondas, no {rounds}"
            )
        self.rounds = rounds

    def hash(self, plain: str) -> str:
        """El hash bcrypt, con sal nueva."""
        return bcrypt.hashpw(_bytes(plain), bcrypt.gensalt(rounds=self.rounds)).decode("utf-8")

    def matches(self, plain: str, hashed: str) -> bool:
        """Si la contraseña casa con el hash (en tiempo constante, lo hace bcrypt)."""
        return bcrypt.checkpw(_bytes(plain), hashed.encode("utf-8"))
