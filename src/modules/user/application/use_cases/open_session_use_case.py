"""
Abrir una sesión para un usuario ya autenticado por otra vía (BE #737).

Verificar el email deja al usuario dentro. Ese camino creaba los dos tokens pero
no registraba el dispositivo ni guardaba el de refresco, y a los 15 minutos el
refresco daba REFRESH_TOKEN_NOT_FOUND: a cada usuario nuevo le echaban. Aquí se
abre como en el login: dispositivo, tokens con su id y refresco guardado.
"""

from dataclasses import dataclass

from src.modules.user.application.dto.device_dto import (
    UNRESOLVED_IP_PLACEHOLDER,
    RegisterDeviceRequestDTO,
)
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.modules.user.application.services.datos_del_acceso import datos_del_acceso
from src.modules.user.application.use_cases.register_device_use_case import (
    RegisterDeviceUseCase,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class SesionAbierta:
    """Los tokens de la sesión y el dispositivo al que pertenece."""

    access_token: str
    refresh_token: str
    device_id: str | None


class OpenSessionUseCase:
    """Abre la sesión de un usuario: dispositivo, tokens y refresco guardado."""

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        token_service: ITokenService,
        register_device_use_case: RegisterDeviceUseCase,
    ):
        self._uow = uow
        self._token_service = token_service
        self._register_device_use_case = register_device_use_case

    async def execute(
        self,
        user_id: str,
        user_agent: str | None,
        ip_address: str | None,
        device_id_from_cookie: str | None,
        installed_app: bool = False,
    ) -> SesionAbierta:
        """
        Abre la sesión y la devuelve.

        Sin User-Agent no hay dispositivo, como en el login: la sesión vale, pero no
        se puede revocar desde la lista.
        """
        device_id: str | None = None
        if user_agent:
            registrado = await self._register_device_use_case.execute(
                RegisterDeviceRequestDTO(
                    user_id=user_id,
                    user_agent=user_agent,
                    ip_address=ip_address or UNRESOLVED_IP_PLACEHOLDER,
                    device_id_from_cookie=device_id_from_cookie,
                    installed_app=installed_app,
                )
            )
            device_id = registrado.device_id

        access_token = self._token_service.create_access_token(
            data=datos_del_acceso(user_id, device_id)
        )
        refresh_token = self._token_service.create_refresh_token(data={"sub": user_id})
        async with self._uow:
            await self._uow.refresh_tokens.save(
                RefreshToken.create(
                    user_id=UserId(user_id),
                    token=refresh_token,
                    device_id=UserDeviceId.from_string(device_id) if device_id else None,
                    expires_in_days=7,
                )
            )
        return SesionAbierta(
            access_token=access_token, refresh_token=refresh_token, device_id=device_id
        )
