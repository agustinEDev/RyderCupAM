"""
Instala el hasher de contraseñas del proceso (auditoría de arquitectura del 9 nov
2026, B2).

Lo llama la composition root (`src/config/dependencies.py`) al importarse, y
también los scripts que crean usuarios sin cargar la app. Las rondas salen de
`BCRYPT_ROUNDS`: 12 si no está (producción); la configuración de los tests pone 4.
`TESTING` ya no las baja: un TESTING olvidado en un despliegue abarataba 256 veces
los hashes nuevos sin avisar (F-06 de la auditoría de seguridad).
"""

import os
from collections.abc import Mapping

from src.modules.user.domain.services.password_hasher import instala_el_hasher
from src.modules.user.infrastructure.security.bcrypt_password_hasher import (
    BcryptPasswordHasher,
)

RONDAS_DE_PRODUCCION = 12


def rondas_de_bcrypt(entorno: Mapping[str, str] = os.environ) -> int:
    """Las rondas de bcrypt configuradas, 12 si no hay ninguna."""
    return int(entorno.get("BCRYPT_ROUNDS", str(RONDAS_DE_PRODUCCION)))


def instala_el_hasher_de_contrasenas() -> None:
    """Instala el adaptador de bcrypt con las rondas configuradas."""
    instala_el_hasher(BcryptPasswordHasher(rounds=rondas_de_bcrypt()))
