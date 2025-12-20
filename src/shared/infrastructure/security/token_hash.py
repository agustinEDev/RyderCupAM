"""
Token Hash Utilities

Utilidades para hashear tokens de forma segura antes de almacenarlos en BD.
Implementa best practices de OWASP para almacenamiento de tokens.

Uso:
- Hashear refresh tokens antes de guardar en BD (previene token theft)
- Los tokens nunca se almacenan en texto plano
- Se usa SHA-256 (suficiente para tokens de vida corta, no passwords)
"""

import hashlib


def hash_token(token: str) -> str:
    """
    Genera un hash SHA-256 del token para almacenamiento seguro.

    NO confundir con password hashing (bcrypt):
    - Passwords: Requieren bcrypt/argon2 (CPU-intensive, salted, slow)
    - Tokens: Requieren SHA-256 (rápido, sin salt necesario)

    Razón: Los tokens ya son valores aleatorios de alta entropía generados
    por JWT con firma criptográfica. No necesitan slow hashing ni salt.

    Args:
        token: Token JWT en texto plano (ej: "eyJhbGciOiJIUzI1...")

    Returns:
        Hash hexadecimal SHA-256 del token (64 caracteres)

    Example:
        >>> token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        >>> hashed = hash_token(token)
        >>> len(hashed)
        64
        >>> hashed[:8]
        'a7f3b2c1'

    Security:
    - SHA-256 es one-way (no reversible)
    - Permite verificar token sin almacenar texto plano
    - OWASP A02: Cryptographic Failures - Protege contra DB leaks
    """
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token_hash(token: str, stored_hash: str) -> bool:
    """
    Verifica si un token coincide con un hash almacenado.

    Args:
        token: Token JWT en texto plano
        stored_hash: Hash almacenado en BD

    Returns:
        True si el token coincide con el hash, False en caso contrario

    Example:
        >>> token = "eyJhbGciOiJIUzI1..."
        >>> hashed = hash_token(token)
        >>> verify_token_hash(token, hashed)
        True
        >>> verify_token_hash("wrong_token", hashed)
        False
    """
    return hash_token(token) == stored_hash
