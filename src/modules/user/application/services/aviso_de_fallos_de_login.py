"""
El correo de «intentos fallidos» al dueño de la cuenta (BE #732).

Cuando una red queda bloqueada para tu cuenta por fallar tu contraseña, o salta el
respaldo de la cuenta (muchas redes a la vez), te llega un correo: desde qué país,
cuándo, que tú puedes seguir entrando desde tus dispositivos, y un botón para
cambiar la contraseña. Sin molestar:
- nunca a un correo sin confirmar;
- como mucho uno por hora y cuenta, contado desde el último enviado;
- y como mucho 20 por hora en toda la app (los provoca un atacante, y el cupo del
  proveedor lo comparten la verificación y la recuperación de contraseña).
El aviso se RESERVA con la fila del usuario bloqueada antes de enviarlo: dos avisos
a la vez no mandan dos correos. Si no sale, se libera. Un fallo nunca tumba nada.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from src.modules.user.application.dto.user_dto import AvisoDeFallosRequestDTO
from src.modules.user.application.ports.aviso_de_fallos_port import IAvisoDeFallos
from src.modules.user.application.ports.cupo_de_avisos_port import ICupoDeAvisos
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.services.aviso_de_nuevo_inicio_de_sesion import (
    cuando_en_espana,
)
from src.modules.user.domain.entities.user import LOCKOUT_DURATION_MINUTES, MAX_FAILED_ATTEMPTS
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.freno_del_login import (
    FALLOS_POR_ORIGEN,
    MINUTOS_DE_BLOQUEO_POR_ORIGEN,
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
        cupo: ICupoDeAvisos,
        reloj: Callable[[], datetime] = datetime.now,
    ):
        self._uow = uow
        self._email_service = email_service
        self._paises = paises
        self._cupo = cupo
        self._reloj = reloj

    async def avisa(self, request: AvisoDeFallosRequestDTO) -> None:
        """Avisa si el correo está confirmado, la cuenta no avisó en la última hora y
        cabe en el tope global."""
        if not request.toca_avisar():
            return
        try:
            ahora = self._reloj()
            # Los números de verdad, no copiados en el texto
            if request.motivo == "respaldo":
                fallos, minutos = MAX_FAILED_ATTEMPTS, LOCKOUT_DURATION_MINUTES
            else:
                fallos, minutos = FALLOS_POR_ORIGEN, MINUTOS_DE_BLOQUEO_POR_ORIGEN
            anterior = await self._reserva(request, ahora)
            if anterior is False:
                return
            try:
                enviado = await self._email_service.send_failed_logins_notification(
                    to_email=request.email,
                    user_name=request.nombre,
                    motivo=request.motivo,
                    cuando=cuando_en_espana(ahora),
                    pais=await self._nombre_del_pais(request.country_code),
                    fallos=fallos,
                    minutos=minutos,
                )
            except Exception:
                await self._libera(request, ahora, anterior)
                raise
            if not enviado:
                logger.warning("Failed sign-ins notice was not sent")
                await self._libera(request, ahora, anterior)
        except Exception as e:
            # Solo el tipo: el mensaje de un proveedor de correo puede llevar la
            # dirección (OWASP A09)
            logger.error("Failed sign-ins notice failed: %s", type(e).__name__)

    async def _reserva(self, request: AvisoDeFallosRequestDTO, ahora: datetime):
        """
        Apunta el aviso con la fila del usuario bloqueada, antes de enviarlo.

        Returns:
            False si no toca (sin cuenta, avisó en la última hora o el tope global
            está lleno); si no, el aviso anterior, para liberar si no sale.
        """
        async with self._uow:
            user = await self._uow.users.find_by_id_for_update(UserId(request.user_id))
            if user is None:
                return False
            anterior = user.failed_login_notice_at
            if anterior and anterior > ahora - UNA_HORA:
                return False
            if not self._cupo.reserva():
                logger.warning("Failed sign-ins notice skipped: hourly budget is full")
                return False
            user.apunta_el_aviso_de_fallos(ahora)
            await self._uow.users.save(user)
        return anterior

    async def _libera(
        self, request: AvisoDeFallosRequestDTO, ahora: datetime, anterior: datetime | None
    ) -> None:
        """Un aviso reservado que no salió: no cuenta para la hora ni para el tope."""
        self._cupo.devuelve()
        try:
            async with self._uow:
                user = await self._uow.users.find_by_id_for_update(UserId(request.user_id))
                if user is not None and user.failed_login_notice_at == ahora:
                    user.devuelve_el_aviso_de_fallos(anterior)
                    await self._uow.users.save(user)
        except Exception as e:
            logger.error("Failed sign-ins notice release failed: %s", type(e).__name__)

    async def _nombre_del_pais(self, codigo: str | None) -> str | None:
        if not codigo:
            return None
        pais = await self._paises.find_by_code(CountryCode(codigo))
        return pais.name_es if pais else codigo
