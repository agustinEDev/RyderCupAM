"""
Instala el hasher de contraseñas del proceso (auditoría de arquitectura del 9 nov
2026, B2).

Lo llama la composition root (`src/config/dependencies/comun.py`) al importarse, y
también los scripts que crean usuarios sin cargar la app. Las rondas salen de
`BCRYPT_ROUNDS`: 12 si no está o no sirve, y menos de 12 solo con
`ENVIRONMENT=development` (local, Kind y los tests, que ponen 4).
`TESTING` ya no las baja: un TESTING olvidado en un despliegue abarataba 256 veces
los hashes nuevos sin avisar (F-06 de la auditoría de seguridad).
"""

import logging
import os
from collections.abc import Mapping

from src.config.env import env_int
from src.modules.user.domain.services.password_hasher import instala_el_hasher
from src.modules.user.infrastructure.security.bcrypt_password_hasher import (
    BcryptPasswordHasher,
)
from src.shared.application.concurrencia.bcrypt_executor import (
    DEFAULT_MAX_CONCURRENCY,
    configura_la_concurrencia_de_bcrypt,
)

RONDAS_DE_PRODUCCION = 12
RONDAS_MINIMAS = 4
RONDAS_MAXIMAS = 15

logger = logging.getLogger(__name__)


def rondas_de_bcrypt(entorno: Mapping[str, str] = os.environ) -> int:
    """Las rondas de bcrypt configuradas, 12 si no hay ninguna o no sirve.

    Raises:
        RuntimeError: con menos de 12 fuera de un desarrollo declarado
            (`ENVIRONMENT=development`); la app no arranca.
    """
    crudo = (entorno.get("BCRYPT_ROUNDS") or "").strip()
    try:
        rondas = int(crudo) if crudo else RONDAS_DE_PRODUCCION
    except ValueError:
        # Vaciar la variable en Render es la forma natural de quitarla, y una
        # errata no debe tumbar el arranque: se usa el coste de producción
        logger.warning(
            "BCRYPT_ROUNDS='%s' no es un entero; se usan %d", crudo, RONDAS_DE_PRODUCCION
        )
        rondas = RONDAS_DE_PRODUCCION
    if not RONDAS_MINIMAS <= rondas <= RONDAS_MAXIMAS:
        # Menos de 4 no lo acepta bcrypt; más de 15 haría que cada login tardara
        # segundos de CPU
        logger.warning(
            "BCRYPT_ROUNDS=%d fuera de %d-%d; se usan %d",
            rondas,
            RONDAS_MINIMAS,
            RONDAS_MAXIMAS,
            RONDAS_DE_PRODUCCION,
        )
        rondas = RONDAS_DE_PRODUCCION
    # Como en rate_limit: un entorno ausente o desconocido cuenta como producción.
    # Solo un desarrollo declarado (local, Kind, los tests) admite un coste bajo
    en_desarrollo = entorno.get("ENVIRONMENT", "").strip().lower() == "development"
    if rondas < RONDAS_DE_PRODUCCION and not en_desarrollo:
        raise RuntimeError(
            f"BCRYPT_ROUNDS={rondas} fuera de desarrollo: el mínimo es {RONDAS_DE_PRODUCCION}"
        )
    return rondas


def instala_el_hasher_de_contrasenas() -> None:
    """
    Instala el adaptador de bcrypt con las rondas configuradas, y fija cuántos
    hashes corren a la vez (`BCRYPT_MAX_CONCURRENCY`, 2 si no está o no sirve).
    """
    instala_el_hasher(BcryptPasswordHasher(rounds=rondas_de_bcrypt()))
    configura_la_concurrencia_de_bcrypt(env_int("BCRYPT_MAX_CONCURRENCY", DEFAULT_MAX_CONCURRENCY))
