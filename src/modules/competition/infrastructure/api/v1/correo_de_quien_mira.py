"""
El correo de quien mira, para casar invitaciones enviadas a una dirección (F-07).

Toda ruta de competition que pase el correo de la sesión (listado, ficha,
inscritos, horarios, partidas) lo saca de aquí: solo el verificado. Sin
verificar, la invitación a esa dirección no existe para esa cuenta. Lo vigila
`test_ninguna_ruta_pasa_el_correo_sin_verificar`.
"""

from src.modules.competition.application.services.correo_del_invitado import (
    correo_del_invitado,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO


def correo_de_quien_mira(current_user: UserResponseDTO) -> str | None:
    """Su correo si lo ha verificado; si no, ninguno."""
    return correo_del_invitado(current_user.email, current_user.email_verified)
