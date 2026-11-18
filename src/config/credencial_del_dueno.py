"""
La credencial del dueño de la base fuera del proceso de la API (DB-R3-01, auditoría del
18 nov 2026).

`MIGRATIONS_DATABASE_URL` solo la necesitan las migraciones. `entrypoint.sh` arranca
uvicorn sin ella; esto es la segunda capa, por si alguien se salta el entrypoint (otro
comando de arranque en Render): la app la borra de su entorno al arrancar y lo avisa.
Arranca igualmente (Agustín, 18 nov): una configuración rara no tira la API.

En desarrollo el `.env` local puede tenerla (`load_dotenv` la mete en el proceso): se
borra con un aviso normal, sin evento de seguridad. Alembic la lee por su cuenta.
"""

import logging
from collections.abc import Callable, MutableMapping

from src.config.migraciones import VARIABLE_DE_LAS_MIGRACIONES
from src.shared.domain.events.security_events import OwnerCredentialInAppEnvironmentAuditEvent
from src.shared.infrastructure.logging.security_logger import get_security_logger

logger = logging.getLogger(__name__)


def retira_la_credencial_del_dueno(
    entorno: MutableMapping[str, str],
    *,
    en_desarrollo: bool,
    avisa: Callable[[], None],
) -> bool:
    """
    Borra MIGRATIONS_DATABASE_URL de `entorno`. True si tenía valor (y se avisó).

    Fuera de desarrollo llama a `avisa` (el evento HIGH); en desarrollo, solo un aviso
    en el log. Nunca se escribe el valor.
    """
    valor = entorno.pop(VARIABLE_DE_LAS_MIGRACIONES, None)
    if not (valor or "").strip():
        return False
    if en_desarrollo:
        logger.warning(
            "%s was in the API environment (local .env?): removed; migrations read it on their own",
            VARIABLE_DE_LAS_MIGRACIONES,
        )
    else:
        avisa()
    return True


def avisa_de_la_credencial_del_dueno() -> None:
    """El evento HIGH del log de seguridad (que lo manda a Sentry)."""
    get_security_logger().log_security_event(
        OwnerCredentialInAppEnvironmentAuditEvent.al_arrancar(VARIABLE_DE_LAS_MIGRACIONES)
    )
