"""Cuánto se puede reanudar una respuesta de refresco perdida (B-19 de la auditoría de la fase 6)."""

from datetime import timedelta

from src.config.env import env_int
from src.modules.user.domain.services.rotacion_del_refresco import VENTANA_DE_LA_REANUDACION

# Más que la hora de antes ya no tendría sentido: sería volver a abrir la ventana de robo
TOPE_DE_LA_VENTANA = timedelta(hours=1)


def ventana_de_la_reanudacion() -> timedelta:
    """
    `REFRESH_RESUME_WINDOW_SECONDS`, 30 minutos por defecto. Un valor que no sea un número
    positivo, o que pase de una hora, vuelve a los 30 minutos: nunca «sin límite».
    """
    defecto = int(VENTANA_DE_LA_REANUDACION.total_seconds())
    segundos = env_int("REFRESH_RESUME_WINDOW_SECONDS", default=defecto)
    if segundos > TOPE_DE_LA_VENTANA.total_seconds():
        return VENTANA_DE_LA_REANUDACION
    return timedelta(seconds=segundos)


# Se lee una vez al arrancar, no en cada refresco (/code-review)
VENTANA_CONFIGURADA = ventana_de_la_reanudacion()
