"""
El correo de «nuevo inicio de sesión», al propio usuario (BE #737).

Si alguien entra en tu cuenta desde un dispositivo que no conocemos, te llega un
correo con qué dispositivo es, cuándo y desde qué país, y un botón para revisar
tus dispositivos. Sin molestar:
- no se envía con el primer dispositivo, el de quien acaba de registrarse;
- ni con un dispositivo ya conocido;
- como mucho uno por hora: si hubo otro dispositivo nuevo hace menos de una hora,
  ya se avisó entonces.
Un fallo al enviarlo nunca tumba el login.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

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

    async def avisa(
        self, user_id: UserId, email: str, nombre: str, device_id: str | None, es_nuevo: bool
    ) -> None:
        """Avisa si el dispositivo es nuevo, no es el primero y no se avisó en la última hora."""
        if not es_nuevo or not device_id:
            return
        try:
            async with self._uow:
                todos = await self._uow.user_devices.find_all_by_user(user_id)
            este = next((d for d in todos if str(d.id.value) == device_id), None)
            otros = [d for d in todos if str(d.id.value) != device_id]
            if este is None or not otros:
                return
            # Como mucho uno por hora: si otro dispositivo nuevo avisó hace menos de una
            # hora, este no. El primero de todos nunca avisó (es el del registro)
            primero = min(todos, key=lambda d: d.created_at)
            hace_una_hora = self._reloj() - UNA_HORA
            if any(d is not primero and d.created_at > hace_una_hora for d in otros):
                return
            await self._email_service.send_new_login_notification(
                to_email=email,
                user_name=nombre,
                dispositivo=nombre_del_dispositivo(este.user_agent, este.installed_app),
                cuando=cuando_en_espana(este.created_at),
                pais=await self._nombre_del_pais(este.country_code),
            )
        except Exception:
            logger.exception("New sign-in notice failed; the login goes on")

    async def _nombre_del_pais(self, codigo: str | None) -> str | None:
        if not codigo:
            return None
        pais = await self._paises.find_by_code(CountryCode(codigo))
        return pais.name_es if pais else codigo
