"""
Puerto para calcular y comprobar el hash de una contraseña.

El dominio decide QUÉ es una contraseña válida (la política) y CUÁNDO se calcula su
hash; CÓMO se calcula (bcrypt, su coste) es infraestructura. El adaptador lo
instala la composition root al cargar (`src/config/contrasenas.py`), y sin él no
se puede crear ni comprobar ninguna contraseña: falla en vez de guardar algo sin
proteger (auditoría de arquitectura del 9 nov 2026, B2).

Es un hasher por proceso, no uno inyectado en cada llamada, porque `Password` es un
value object que se construye en muchos sitios (la entidad `User`, los casos de uso,
los tests) y el algoritmo no cambia entre peticiones.
"""

from typing import Protocol


class PasswordHasher(Protocol):
    """Calcula y comprueba hashes de contraseñas."""

    def hash(self, plain: str) -> str:
        """El hash de la contraseña, con su sal y su coste dentro."""
        ...

    def matches(self, plain: str, hashed: str) -> bool:
        """Si la contraseña casa con el hash."""
        ...


class HasherNoInstaladoError(RuntimeError):
    """Se pidió un hash sin que la composition root instalara el hasher."""


_instalado: PasswordHasher | None = None


def instala_el_hasher(hasher: PasswordHasher) -> None:
    """Lo llama la composition root al arrancar."""
    global _instalado  # noqa: PLW0603 - un único hasher por proceso, a propósito
    _instalado = hasher


def hasher_de_contrasenas() -> PasswordHasher:
    """El hasher instalado.

    Raises:
        HasherNoInstaladoError: si nadie lo instaló.
    """
    if _instalado is None:
        raise HasherNoInstaladoError(
            "No hay PasswordHasher instalado: lo instala src.config.contrasenas"
        )
    return _instalado
