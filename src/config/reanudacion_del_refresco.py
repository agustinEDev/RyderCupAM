"""Cuánto se puede reanudar una respuesta de refresco perdida (B-19 de la auditoría de la fase 6)."""

from datetime import timedelta

from src.config.env import env_int
from src.modules.user.domain.services.rotacion_del_refresco import VENTANA_DE_LA_REANUDACION


def ventana_de_la_reanudacion() -> timedelta:
    """
    Cuánto se puede reanudar una respuesta de refresco perdida (B-19 de la auditoría de la
    fase 6): `REFRESH_RESUME_WINDOW_SECONDS`, 5 minutos por defecto. Un valor que no sea
    un número positivo vuelve a los 5 minutos, nunca a «sin límite».
    """
    return timedelta(
        seconds=env_int(
            "REFRESH_RESUME_WINDOW_SECONDS",
            default=int(VENTANA_DE_LA_REANUDACION.total_seconds()),
        )
    )
