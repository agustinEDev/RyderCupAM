"""
Cerrar todas las sesiones de una cuenta: sus dispositivos y sus tokens de refresco.

Lo usan desactivar o reactivar una cuenta (BE #744) y la toma de una cuenta sin
verificar por un Google que verificó su correo: una sola regla de qué es «cerrar
todo». Dentro de la transacción del que llama.
"""

from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


async def revoca_sus_sesiones(uow: UserUnitOfWorkInterface, user_id: UserId) -> tuple[int, int]:
    """Revoca sus dispositivos activos y sus tokens de refresco. Devuelve cuántos de cada."""
    dispositivos = await uow.user_devices.find_active_by_user(user_id)
    for dispositivo in dispositivos:
        dispositivo.revoke()
        await uow.user_devices.save(dispositivo)
    tokens = await uow.refresh_tokens.revoke_all_for_user(user_id)
    return len(dispositivos), tokens
