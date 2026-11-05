"""
El correo de «nuevo inicio de sesión», al propio usuario (BE #737).

Si alguien entra en tu cuenta desde un dispositivo que no conocemos, te llega un
correo con qué dispositivo es, cuándo y desde qué país, y un botón para revisar
tus dispositivos. Sin molestar:
- solo con un dispositivo que llega sin su cookie: uno nuevo, aunque sea el único
  (tras la limpieza de 30 días también puede ser un intruso), o uno que reconoce
  solo la huella (con el mismo móvil y la misma red, la huella no distingue a otra
  persona);
- nunca a un correo sin confirmar: solo le llega el de confirmación, y no mandamos
  correos de seguridad a una dirección que quizá no es suya;
- ni en el alta con Google, que es crear la cuenta;
- como mucho uno por dispositivo y hora, contado desde su último correo enviado:
  el aviso de un dispositivo no tapa el de otro.
Un fallo al enviarlo nunca tumba el login, y no cuenta como enviado.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from src.modules.user.application.dto.device_dto import AvisoDeNuevoInicioRequestDTO
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.descripcion_del_dispositivo import describe_el_dispositivo
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.domain.value_objects.country_code import CountryCode

logger = logging.getLogger(__name__)

UNA_HORA = timedelta(hours=1)
HORA_DE_ESPANA = ZoneInfo("Europe/Madrid")
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

PLATAFORMAS = {
    "iphone": "iPhone",
    "ipad": "iPad",
    "mac": "Mac",
    "android": "Android",
    "windows": "Windows",
    "chromebook": "Chromebook",
    "linux": "Linux",
}
NAVEGADORES = {
    "safari": "Safari",
    "chrome": "Chrome",
    "firefox": "Firefox",
    "edge": "Edge",
    "opera": "Opera",
    "samsung": "Samsung Internet",
    "instagram": "navegador de Instagram",
    "google": "app de Google",
    "facebook": "navegador de Facebook",
}


def nombre_del_dispositivo(user_agent: str | None, instalada: bool) -> str:
    """«iPhone · Safari», «iPhone · app instalada» o «Dispositivo desconocido»."""
    descripcion = describe_el_dispositivo(user_agent)
    plataforma = PLATAFORMAS.get(descripcion.plataforma)
    if plataforma is None:
        return "Dispositivo desconocido"
    if instalada:
        return f"{plataforma} · app instalada"
    navegador = NAVEGADORES.get(descripcion.navegador)
    return f"{plataforma} · {navegador}" if navegador else plataforma


def cuando_en_espana(instante_utc: datetime) -> str:
    """«5 nov 2026, 20:07 (hora de España)», desde una fecha UTC sin huso."""
    local = instante_utc.replace(tzinfo=UTC).astimezone(HORA_DE_ESPANA)
    return f"{local.day} {MESES[local.month - 1]} {local.year}, {local:%H:%M} (hora de España)"


class AvisoDeNuevoInicioDeSesion:
    """Decide si toca avisar de un nuevo inicio de sesión y, si toca, envía el correo."""

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

    async def avisa(self, request: AvisoDeNuevoInicioRequestDTO) -> None:
        """Avisa si el dispositivo llegó sin su cookie, el correo está confirmado, no es
        el alta y este dispositivo no avisó en la última hora."""
        if (
            not request.desconocido
            or not request.device_id
            or not request.verificado
            or request.es_alta
        ):
            return
        try:
            async with self._uow:
                todos = await self._uow.user_devices.find_all_by_user(UserId(request.user_id))
            este = next((d for d in todos if str(d.id.value) == request.device_id), None)
            if este is None:
                return
            ahora = self._reloj()
            hace_una_hora = ahora - UNA_HORA
            # Uno por dispositivo y hora: el aviso de uno no tapa el de otro
            if este.aviso_enviado_at and este.aviso_enviado_at > hace_una_hora:
                return
            enviado = await self._email_service.send_new_login_notification(
                to_email=request.email,
                user_name=request.nombre,
                dispositivo=nombre_del_dispositivo(este.user_agent, este.installed_app),
                cuando=cuando_en_espana(este.created_at),
                pais=await self._nombre_del_pais(este.country_code),
            )
            # Enviado: cuenta para el tope de uno por hora. Uno que no salió, no
            if not enviado:
                logger.warning("New sign-in notice was not sent")
                return
            async with self._uow:
                este.apunta_el_aviso(ahora)
                await self._uow.user_devices.save(este)
        except Exception as e:
            # Solo el tipo: el mensaje de un proveedor de correo puede llevar la
            # dirección (auditoría OWASP, A09)
            logger.error("New sign-in notice failed; the login goes on: %s", type(e).__name__)

    async def _nombre_del_pais(self, codigo: str | None) -> str | None:
        if not codigo:
            return None
        pais = await self._paises.find_by_code(CountryCode(codigo))
        return pais.name_es if pais else codigo
