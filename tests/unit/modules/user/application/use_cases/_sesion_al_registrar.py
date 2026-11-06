"""
Un UoW en memoria donde dar de alta un dispositivo es entrar con él (BE #737).

Desde BE #737 la lista solo enseña los dispositivos con una sesión abierta, es
decir, con algún refresh token vivo. Los tests que registran dispositivos sin
pasar por el login los dan de alta así, con su sesión, como en la app.
"""

from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


def uow_con_sesion_al_registrar() -> InMemoryUnitOfWork:
    """Un UoW en memoria cuyos dispositivos nuevos nacen con un refresh token vivo."""
    uow = InMemoryUnitOfWork()
    original = uow.user_devices.add_unless_registered

    async def alta_con_sesion(device):
        """Da de alta el dispositivo y, si es nuevo, le abre una sesión."""
        guardado = await original(device)
        if guardado is device:
            await uow.refresh_tokens.save(
                RefreshToken.create(
                    user_id=device.user_id,
                    token=f"refresco-de-{device.id.value}",
                    device_id=device.id,
                    expires_in_days=7,
                )
            )
        return guardado

    uow.user_devices.add_unless_registered = alta_con_sesion
    return uow
