"""
El correo de «intentos fallidos» al dueño de la cuenta (BE #732).

Cuando una red queda bloqueada para tu cuenta por fallar tu contraseña, o salta el
respaldo de la cuenta (muchas redes a la vez), te llega un correo: desde qué país,
cuándo, que tú puedes seguir entrando desde tus dispositivos, y un botón para
cambiar la contraseña. Sin molestar:
- nunca a un correo sin confirmar;
- como mucho uno por hora y cuenta, contado desde el último enviado.
Un fallo al enviarlo nunca tumba nada, y no cuenta como enviado.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from src.modules.user.application.dto.user_dto import AvisoDeFallosRequestDTO
from src.modules.user.application.ports.aviso_de_fallos_port import IAvisoDeFallos
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.services.aviso_de_nuevo_inicio_de_sesion import (
    cuando_en_espana,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.domain.value_objects.country_code import CountryCode

logger = logging.getLogger(__name__)

UNA_HORA = timedelta(hours=1)


class AvisoDeFallosDeLogin(IAvisoDeFallos):
    """Decide si toca avisar de los intentos fallidos y, si toca, envía el correo."""

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        email_service: IEmailService,
        paises: CountryRepositoryInterface,
        reloj: Callable[[], datetime] = datetime.now,
    ):
        self._uow = uow
        self._email_service = email_service
        self._paises = paises
        self._reloj = reloj

    async def avisa(self, request: AvisoDeFallosRequestDTO) -> None:
        """Avisa si el correo está confirmado y la cuenta no avisó en la última hora."""
        if not request.toca_avisar():
            return
        try:
            async with self._uow:
                user = await self._uow.users.find_by_id(UserId(request.user_id))
            if user is None:
                return
            ahora = self._reloj()
            if user.failed_login_notice_at and user.failed_login_notice_at > ahora - UNA_HORA:
                return
            enviado = await self._email_service.send_failed_logins_notification(
                to_email=request.email,
                user_name=request.nombre,
                motivo=request.motivo,
                cuando=cuando_en_espana(ahora),
                pais=await self._nombre_del_pais(request.country_code),
            )
            if not enviado:
                logger.warning("Failed sign-ins notice was not sent")
                return
            async with self._uow:
                user.apunta_el_aviso_de_fallos(ahora)
                await self._uow.users.save(user)
        except Exception as e:
            # Solo el tipo: el mensaje de un proveedor de correo puede llevar la
            # dirección (OWASP A09)
            logger.error("Failed sign-ins notice failed: %s", type(e).__name__)

    async def _nombre_del_pais(self, codigo: str | None) -> str | None:
        if not codigo:
            return None
        pais = await self._paises.find_by_code(CountryCode(codigo))
        return pais.name_es if pais else codigo
