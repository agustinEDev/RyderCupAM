"""La hora actual tal como se guardan las fechas: en UTC y sin zona."""

from datetime import datetime

from src.shared.domain.services.instante_utc import ahora_utc_sin_zona


def utc_now() -> datetime:
    """
    Ahora, en UTC y sin zona: el mismo reloj que `ahora_utc_sin_zona` (re-auditoría
    F-02). Lo usan los módulos que ya lo importaban; lo nuevo, el de `instante_utc`.
    """
    return ahora_utc_sin_zona()
