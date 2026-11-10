"""
El correo «Hemos cerrado tu sesión en un dispositivo por seguridad» (F-02, caso A4).

Cuando llega un refresh token ya sustituido cuyo sustituto ya se usó, dos sitios tienen
la misma sesión: se revocan los tokens de ese dispositivo y se avisa al usuario con
qué dispositivo era, cuándo y desde qué país, y un botón para revisar sus dispositivos.
Como los demás avisos de seguridad, nunca a un correo sin confirmar, y con el tope
global de avisos (`cupo_de_avisos`, su propio hueco): los provoca quien tenga cookies
robadas. Un fallo al enviarlo nunca tumba el refresco y devuelve su hueco.
"""

import logging
from collections.abc import Callable
from datetime import datetime

from src.modules.user.application.dto.device_dto import AvisoDeSesionCerradaRequestDTO
from src.modules.user.application.ports.aviso_de_sesion_cerrada_port import (
    IAvisoDeSesionCerrada,
)
from src.modules.user.application.ports.cupo_de_avisos_port import (
    MOTIVO_SESION_CERRADA,
    ICupoDeAvisos,
)
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.services.aviso_de_nuevo_inicio_de_sesion import (
    cuando_en_espana,
    nombre_del_dispositivo,
    nombre_del_pais,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)

logger = logging.getLogger(__name__)


class AvisoDeSesionCerradaPorSeguridad(IAvisoDeSesionCerrada):
    """Manda el correo de la sesión cerrada por seguridad, si toca."""

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        email_service: IEmailService,
        paises: CountryRepositoryInterface,
        cupo: ICupoDeAvisos,
        reloj: Callable[[], datetime] = datetime.now,
    ):
        self._uow = uow
        self._email_service = email_service
        self._paises = paises
        self._cupo = cupo
        self._reloj = reloj

    async def avisa(self, request: AvisoDeSesionCerradaRequestDTO) -> None:
        """Avisa si el correo está confirmado y el dispositivo es suyo."""
        if not request.toca_avisar():
            return
        try:
            # Por id, no `find_by_id_and_user`: ese solo da los activos, y el robo acaba
            # de revocar este
            async with self._uow:
                dispositivo = await self._uow.user_devices.find_by_id(
                    UserDeviceId.from_string(request.device_id)
                )
        except Exception as e:
            logger.error("Session closed for security notice failed: %s", type(e).__name__)
            return
        if dispositivo is None or dispositivo.user_id != UserId(request.user_id):
            return
        if not self._cupo.reserva(MOTIVO_SESION_CERRADA):
            logger.warning("Session closed for security notice skipped: the budget is full")
            return
        enviado = False
        try:
            enviado = await self._email_service.send_session_closed_for_security_notice(
                to_email=request.email,
                user_name=request.nombre,
                dispositivo=nombre_del_dispositivo(
                    dispositivo.user_agent, dispositivo.installed_app
                ),
                cuando=cuando_en_espana(self._reloj()),
                pais=await nombre_del_pais(self._paises, dispositivo.country_code),
            )
            if not enviado:
                logger.warning("Session closed for security notice was not sent")
        except Exception as e:
            # Solo el tipo: el mensaje de un proveedor de correo puede llevar la
            # dirección (OWASP A09)
            logger.error("Session closed for security notice failed: %s", type(e).__name__)
        finally:
            # Uno que no salió no gasta el tope
            if not enviado:
                self._cupo.devuelve(MOTIVO_SESION_CERRADA)
