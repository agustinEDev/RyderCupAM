"""
Abrir una sesión para un usuario ya autenticado por otra vía (BE #737).

Verificar el email deja al usuario dentro. Ese camino creaba los dos tokens pero
no registraba el dispositivo ni guardaba el de refresco, y a los 15 minutos el
refresco daba REFRESH_TOKEN_NOT_FOUND: a cada usuario nuevo le echaban. Aquí se
abre como en el login: dispositivo, tokens con su id y refresco guardado.
"""

from src.modules.user.application.dto.device_dto import (
    UNRESOLVED_IP_PLACEHOLDER,
    OpenSessionRequestDTO,
    OpenSessionResponseDTO,
    RegisterDeviceRequestDTO,
    agente_para_el_registro,
)
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.modules.user.application.services.datos_del_acceso import datos_del_acceso
from src.modules.user.application.use_cases.register_device_use_case import (
    RegisterDeviceUseCase,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.exceptions import AccountDeactivatedException
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId


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

    async def execute(self, request: OpenSessionRequestDTO) -> OpenSessionResponseDTO:
        """
        Abre la sesión y la devuelve.

        Siempre con dispositivo, también sin User-Agent: una sesión sin él no salía
        en la lista, no avisaba y no se podía revocar (auditoría OWASP, A07).

        Raises:
            AccountDeactivatedException: si la cuenta está desactivada (BE #744): la
                regla vive aquí, y vale para cualquier camino que abra una sesión
        """
        user = await self._uow.users.find_by_id(UserId(request.user_id))
        if user is None or not user.is_active:
            raise AccountDeactivatedException()
        registrado = await self._register_device_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=request.user_id,
                user_agent=agente_para_el_registro(request.user_agent),
                ip_address=request.ip_address or UNRESOLVED_IP_PLACEHOLDER,
                device_id_from_cookie=request.device_id_from_cookie,
                installed_app=request.installed_app,
                country_code=request.country_code,
            )
        )
        device_id = registrado.device_id

        access_token = self._token_service.create_access_token(
            data=datos_del_acceso(request.user_id, device_id)
        )
        refresh_token = self._token_service.create_refresh_token(data={"sub": request.user_id})
        async with self._uow:
            await self._uow.refresh_tokens.save(
                RefreshToken.create(
                    user_id=UserId(request.user_id),
                    token=refresh_token,
                    device_id=UserDeviceId.from_string(device_id),
                    expires_in_days=7,
                )
            )
        return OpenSessionResponseDTO(
            access_token=access_token, refresh_token=refresh_token, device_id=device_id
        )
