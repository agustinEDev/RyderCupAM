"""
Lo que no se probó de una cuenta SIN verificar, fuera (#749, pre-captura).

Cuando alguien demuestra que el correo de una cuenta sin verificar es suyo (entra con
un Google que lo verificó, o restablece la contraseña con el enlace de su buzón), lo
que dejó quien la creó o le cambió el correo no vale: sus dispositivos, sus sesiones y
el Google que hubiera vinculado. Dentro de la transacción del que llama.
"""

from src.modules.user.application.services.revoca_sus_sesiones import revoca_sus_sesiones
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_id import UserId


async def cierra_lo_que_no_se_probo(
    uow: UserUnitOfWorkInterface, user_id: UserId
) -> tuple[int, int, int]:
    """Revoca dispositivos y sesiones y quita su Google. Devuelve cuántos de cada."""
    dispositivos, tokens = await revoca_sus_sesiones(uow, user_id)
    google = await uow.oauth_accounts.find_by_user_id_and_provider(user_id, OAuthProvider.GOOGLE)
    if google is not None:
        await uow.oauth_accounts.delete(google)
    return dispositivos, tokens, int(google is not None)
