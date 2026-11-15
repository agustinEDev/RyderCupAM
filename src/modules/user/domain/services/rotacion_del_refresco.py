"""
La regla de la rotación del refresh token (F-02 de la auditoría).

Cada refresco sustituye el token por un sucesor. Cuando llega uno ya sustituido, lo
que toca depende de cuándo se sustituyó y de si su sustituto ya se usó: dos pestañas a
la vez, una respuesta perdida o un robo. Tabla aprobada por Agustín (10 nov 2026).
"""

from datetime import datetime, timedelta
from enum import Enum

from src.modules.user.domain.entities.refresh_token import RefreshToken

# Una respuesta perdida se reintenta enseguida: pasados 5 minutos desde la sustitución,
# la cookie vieja con el sustituto sin usar ya no se reanuda. Tampoco es un robo: se
# rechaza sin alarma y el usuario vuelve a entrar (Agustín, 10 nov 2026). Era 1 hora;
# 5 minutos desde B-19 de la auditoría de la fase 6 (Agustín, 15 nov 2026): en esa
# ventana también podría reanudar quien hubiera robado la cookie vieja
VENTANA_DE_LA_REANUDACION = timedelta(minutes=5)


class PasoDelRefresco(Enum):
    """Qué hacer con el token que llega."""

    ROTA = "rota"  # vigente: refresh nuevo (A1)
    SOLO_ACCESO = "solo_acceso"  # dos pestañas: access nuevo, sin otro refresh (A2)
    REANUDA = "reanuda"  # respuesta perdida: rota otra vez y anula el sustituto (A3)
    ROBO = "robo"  # alguien más tiene la sesión (A4)
    REANUDACION_CADUCADA = "reanudacion_caducada"  # pasada la ventana sin usar el sustituto
    YA_CERRADA = "ya_cerrada"  # su sustituto se cerró por otra vía: rechazo


def sustituto_usado(sustituto: RefreshToken) -> bool:
    """Un sustituto está usado cuando ya rotó: alguien lo presentó y obtuvo otro."""
    return sustituto.is_replaced


def paso_del_refresco(
    token: RefreshToken,
    sustituto: RefreshToken | None,
    ahora: datetime,
    ventana: timedelta = VENTANA_DE_LA_REANUDACION,
) -> PasoDelRefresco:
    """
    El paso para `token`, ya comprobado que no está caducado y que, salvo que sea un
    sustituto anulado, no está revocado. `sustituto` es su último sucesor, si lo tiene.

    - Un sustituto anulado que vuelve: ROBO (nunca llegó al navegador legítimo).
    - Vigente: ROTA.
    - Su sustituto revocado, caducado o inexistente: YA_CERRADA.
    - Dentro del margen de 60 s, usado o no el sustituto: SOLO_ACCESO.
    - Fuera del margen con el sustituto ya usado: ROBO.
    - Fuera del margen, sustituto sin usar, pasada la ventana: REANUDACION_CADUCADA.
    - Si no: REANUDA.
    """
    if token.is_annulled:
        return PasoDelRefresco.ROBO
    if not token.is_replaced or token.replaced_at is None:
        return PasoDelRefresco.ROTA
    if sustituto is None or sustituto.revoked or sustituto.is_expired():
        return PasoDelRefresco.YA_CERRADA
    if token.en_el_margen(ahora):
        return PasoDelRefresco.SOLO_ACCESO
    return _fuera_del_margen(token.replaced_at, sustituto, ahora, ventana)


def _fuera_del_margen(
    sustituido_en: datetime, sustituto: RefreshToken, ahora: datetime, ventana: timedelta
) -> PasoDelRefresco:
    """Pasado el margen de dos pestañas: robo, reanudación o reanudación caducada."""
    if sustituto_usado(sustituto):
        return PasoDelRefresco.ROBO
    if ahora - sustituido_en > ventana:
        return PasoDelRefresco.REANUDACION_CADUCADA
    return PasoDelRefresco.REANUDA
