"""
Quien me bloqueó no existe para mí (F-09, fase 3 del plan a 9, 10 nov 2026).

Lo que pida de él (perfil, avatar, actividad, partidas juntos, galería, mandarle
una solicitud, encontrarle en la búsqueda) responde como una cuenta que no está:
sin pistas de que hay un bloqueo. Si lo bloqueé yo, todo como antes: lo sé, y
desde su perfil se desbloquea (opción A de Agustín).
"""

from src.modules.social.domain.repositories.friendship_repository_interface import (
    FriendshipRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


async def me_bloqueo(
    friendships: FriendshipRepositoryInterface, quien_mira: UserId, otro: UserId
) -> bool:
    """
    Si `otro` bloqueó a `quien_mira` y `quien_mira` no le bloqueó a él (no al revés).
    Si se bloquearon los dos, no: lo ve como un bloqueo suyo (SB-02). Con el `uow`
    ya abierto.
    """
    if quien_mira == otro:
        return False
    relacion = await friendships.find_by_pair(quien_mira, otro)
    return relacion is not None and relacion.lo_oculta_a(quien_mira)
