"""
Guardar una sesión solo si la cuenta sigue valiendo (#749, tabla de caminos).

Entre comprobar la credencial y guardar la sesión pasa tiempo (el bcrypt, Google, el
registro del dispositivo): otra petición puede quedarse la cuenta, desactivarla,
cambiarle la contraseña o quitarle el Google. Aquí se bloquea la fila, se vuelve a
comprobar sobre ella y se guarda en la misma transacción; si ya no vale, no hay sesión
y el dispositivo que dio de alta este login se revoca.
"""

from collections.abc import Awaitable, Callable

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId

# El motivo de un rechazo por una cuenta desactivada: se responde como siempre (403)
CUENTA_DESACTIVADA = "Account deactivated by admin"


async def guarda_la_sesion(
    uow: UserUnitOfWorkInterface,
    user_id: UserId,
    comprueba: Callable[[User | None], Awaitable[str | None]],
    guarda: Callable[[], Awaitable[None]],
    dispositivo_nuevo: UserDeviceId | None,
) -> str | None:
    """
    Con la fila bloqueada: `comprueba` la cuenta releída; si vale, `guarda`.

    Returns:
        None si se guardó; si no, el motivo (y `dispositivo_nuevo`, si lo hay, revocado)
    """
    async with uow:
        actual = await uow.users.find_by_id_for_update(user_id)
        motivo = await comprueba(actual)
        if motivo is None:
            await guarda()
        elif dispositivo_nuevo is not None:
            dispositivo = await uow.user_devices.find_by_id(dispositivo_nuevo)
            if dispositivo is not None and dispositivo.is_active:
                dispositivo.revoke()
                await uow.user_devices.save(dispositivo)
    return motivo


async def activa(actual: User | None) -> str | None:
    """La comprobación mínima: que la cuenta exista y esté activa."""
    if actual is None:
        return "Account deleted during sign-in"
    if not actual.is_active:
        return CUENTA_DESACTIVADA
    return None
