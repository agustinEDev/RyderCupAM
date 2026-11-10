"""
Los avisos de seguridad por correo, en segundo plano: el de «nuevo inicio de sesión»
(BE #737), el de «intentos fallidos» (BE #732), el de «sesión cerrada por seguridad»
(F-02: robo de un refresh token; el refresco tampoco espera) y los correos del
registro y del reenvío de la verificación (fase 3: la respuesta no espera al
proveedor y tarda lo mismo exista o no el correo).

El login contesta sin esperar al proveedor de correo: el aviso se lanza como una
tarea del propio proceso, con su propia sesión de BD, porque la de la petición se
cierra al contestar. Si el proceso se reinicia justo entonces, ese correo se pierde
(decidido así: el login no espera).
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.modules.user.application.dto.device_dto import (
    AvisoDeNuevoInicioRequestDTO,
    AvisoDeSesionCerradaRequestDTO,
)
from src.modules.user.application.dto.user_dto import AvisoDeFallosRequestDTO
from src.modules.user.application.ports.aviso_de_fallos_port import IAvisoDeFallos
from src.modules.user.application.ports.aviso_de_nuevo_inicio_port import IAvisoDeNuevoInicio
from src.modules.user.application.ports.aviso_de_sesion_cerrada_port import (
    IAvisoDeSesionCerrada,
)
from src.modules.user.application.ports.correo_en_segundo_plano_port import (
    ICorreoEnSegundoPlano,
)
from src.modules.user.application.ports.cupo_de_avisos_port import ICupoDeAvisos
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.reenvio_de_verificacion_port import (
    IReenvioDeVerificacion,
    ReenvioDeVerificacion,
)
from src.modules.user.application.services.aviso_de_fallos_de_login import (
    AvisoDeFallosDeLogin,
)
from src.modules.user.application.services.aviso_de_nuevo_inicio_de_sesion import (
    AvisoDeNuevoInicioDeSesion,
)
from src.modules.user.application.services.aviso_de_sesion_cerrada_por_seguridad import (
    AvisoDeSesionCerradaPorSeguridad,
)
from src.modules.user.application.services.envio_de_la_verificacion import (
    EnvioDeLaVerificacion,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)
from src.shared.infrastructure.persistence.sqlalchemy.country_repository import (
    SQLAlchemyCountryRepository,
)

logger = logging.getLogger(__name__)

# Las tareas en marcha: asyncio solo guarda referencias débiles, y una tarea sin
# referencia la puede recoger el recolector antes de acabar
_PENDIENTES: set[asyncio.Task[None]] = set()


async def espera_los_avisos_pendientes(tope_s: float | None = None) -> None:
    """
    Espera a los avisos en marcha de ESTE bucle de eventos (para los tests; producción
    no los espera, ni al apagar).

    Los de un bucle ya cerrado (un test anterior que no los esperó) no van a acabar
    nunca ni se pueden esperar desde aquí: se descartan. Con `tope_s`, si alguno no
    acaba a tiempo lanza TimeoutError con sus nombres, sin cancelarlo (BE #781).

    Raises:
        TimeoutError: si pasado `tope_s` queda alguno en marcha
    """
    bucle = asyncio.get_running_loop()
    limite = None if tope_s is None else bucle.time() + tope_s
    while True:
        # Sobre una copia: el callback que quita una tarea puede correr en otro hilo
        for tarea in [t for t in tuple(_PENDIENTES) if t.get_loop().is_closed()]:
            _PENDIENTES.discard(tarea)
        mias = [t for t in tuple(_PENDIENTES) if t.get_loop() is bucle and not t.done()]
        if not mias:
            return
        restante = None if limite is None else limite - bucle.time()
        _, sin_acabar = await asyncio.wait(mias, timeout=restante)
        if sin_acabar and limite is not None and bucle.time() >= limite:
            nombres = ", ".join(sorted(t.get_name() for t in sin_acabar))
            raise TimeoutError(f"Avisos en segundo plano sin acabar tras {tope_s} s: {nombres}")


class AvisoEnSegundoPlano(IAvisoDeNuevoInicio):
    """Lanza el aviso sin que el login lo espere."""

    def __init__(self, fabrica: async_sessionmaker[AsyncSession], email_service: IEmailService):
        """Con la fábrica de sesiones y el servicio de correo."""
        self._fabrica = fabrica
        self._email_service = email_service

    async def avisa(self, request: AvisoDeNuevoInicioRequestDTO) -> None:
        """Lanza el aviso y vuelve enseguida. Si no toca avisar, ni lo lanza."""
        if not request.toca_avisar():
            return
        # Con nombre: si un test se queda esperándola, el TimeoutError dice cuál es
        tarea = asyncio.create_task(self._avisa(request), name="aviso-de-nuevo-inicio")
        _PENDIENTES.add(tarea)
        tarea.add_done_callback(_PENDIENTES.discard)

    async def _avisa(self, request: AvisoDeNuevoInicioRequestDTO) -> None:
        """El aviso, con su propia sesión de BD: la de la petición ya se cerró."""
        try:
            async with self._fabrica() as sesion:
                aviso = AvisoDeNuevoInicioDeSesion(
                    SQLAlchemyUnitOfWork(sesion),
                    self._email_service,
                    SQLAlchemyCountryRepository(sesion),
                )
                await aviso.avisa(request)
        except Exception as e:
            # Solo el tipo: el mensaje puede llevar la dirección (auditoría OWASP, A09)
            logger.error("New sign-in notice failed in the background: %s", type(e).__name__)


class AvisoDeFallosEnSegundoPlano(IAvisoDeFallos):
    """Lanza el aviso de intentos fallidos sin que el login lo espere (BE #732)."""

    def __init__(
        self,
        fabrica: async_sessionmaker[AsyncSession],
        email_service: IEmailService,
        cupo: ICupoDeAvisos,
    ):
        """Con la fábrica de sesiones y el servicio de correo."""
        self._fabrica = fabrica
        self._email_service = email_service
        self._cupo = cupo

    async def avisa(self, request: AvisoDeFallosRequestDTO) -> None:
        """Lanza el aviso y vuelve enseguida. Si no toca avisar, ni lo lanza."""
        if not request.toca_avisar():
            return
        tarea = asyncio.create_task(self._avisa(request), name="aviso-de-intentos-fallidos")
        _PENDIENTES.add(tarea)
        tarea.add_done_callback(_PENDIENTES.discard)

    async def _avisa(self, request: AvisoDeFallosRequestDTO) -> None:
        """El aviso, con su propia sesión de BD: la de la petición ya se cerró."""
        try:
            async with self._fabrica() as sesion:
                aviso = AvisoDeFallosDeLogin(
                    SQLAlchemyUnitOfWork(sesion),
                    self._email_service,
                    SQLAlchemyCountryRepository(sesion),
                    self._cupo,
                )
                await aviso.avisa(request)
        except Exception as e:
            # Solo el tipo: el mensaje puede llevar la dirección (OWASP A09)
            logger.error("Failed sign-ins notice failed in the background: %s", type(e).__name__)


class CorreoEnSegundoPlano(ICorreoEnSegundoPlano):
    """Lanza un correo del registro sin que la respuesta lo espere (fase 3, B1-B3)."""

    def lanza(self, nombre: str, envio: Callable[[], Awaitable[object]]) -> None:
        """Lo lanza como tarea del proceso, registrada para que los tests la esperen."""
        tarea = asyncio.create_task(self._envia(nombre, envio), name=nombre)
        _PENDIENTES.add(tarea)
        tarea.add_done_callback(_PENDIENTES.discard)

    @staticmethod
    async def _envia(nombre: str, envio: Callable[[], Awaitable[object]]) -> None:
        """El envío; un fallo se queda en el log, solo con su tipo (OWASP A09)."""
        try:
            await envio()
        except Exception as e:
            logger.error("Background email %s failed: %s", nombre, type(e).__name__)


class ReenvioEnSegundoPlano(IReenvioDeVerificacion):
    """Envía el enlace de verificación nuevo y, si sale, lo guarda; sin que la petición
    espere (fase 3, revisión). Con su propia sesión de BD: la de la petición se cierra."""

    def __init__(self, fabrica: async_sessionmaker[AsyncSession], email_service: IEmailService):
        """Con la fábrica de sesiones y el servicio de correo."""
        self._fabrica = fabrica
        self._email_service = email_service

    def lanza(self, datos: ReenvioDeVerificacion) -> None:
        """Lo lanza como tarea del proceso, registrada para que los tests la esperen."""
        tarea = asyncio.create_task(self._envia(datos), name="reenvio-de-verificacion")
        _PENDIENTES.add(tarea)
        tarea.add_done_callback(_PENDIENTES.discard)

    async def _envia(self, datos: ReenvioDeVerificacion) -> None:
        """El envío y el guardado; un fallo se queda en el log, solo con su tipo (A09)."""
        try:
            async with self._fabrica() as sesion:
                await EnvioDeLaVerificacion(
                    SQLAlchemyUnitOfWork(sesion), self._email_service
                ).envia_y_guarda(datos)
        except Exception as e:
            logger.error("Verification resend failed in the background: %s", type(e).__name__)


class AvisoDeSesionCerradaEnSegundoPlano(IAvisoDeSesionCerrada):
    """Lanza el aviso de la sesión cerrada por seguridad sin que el refresco lo espere (F-02)."""

    def __init__(
        self,
        fabrica: async_sessionmaker[AsyncSession],
        email_service: IEmailService,
        cupo: ICupoDeAvisos,
    ):
        """Con la fábrica de sesiones, el servicio de correo y el tope global de avisos."""
        self._fabrica = fabrica
        self._email_service = email_service
        self._cupo = cupo

    async def avisa(self, request: AvisoDeSesionCerradaRequestDTO) -> None:
        """Lanza el aviso y vuelve enseguida. Si no toca avisar, ni lo lanza."""
        if not request.toca_avisar():
            return
        tarea = asyncio.create_task(self._avisa(request), name="aviso-de-sesion-cerrada")
        _PENDIENTES.add(tarea)
        tarea.add_done_callback(_PENDIENTES.discard)

    async def _avisa(self, request: AvisoDeSesionCerradaRequestDTO) -> None:
        """El aviso, con su propia sesión de BD: la de la petición ya se cerró."""
        try:
            async with self._fabrica() as sesion:
                aviso = AvisoDeSesionCerradaPorSeguridad(
                    SQLAlchemyUnitOfWork(sesion),
                    self._email_service,
                    SQLAlchemyCountryRepository(sesion),
                    self._cupo,
                )
                await aviso.avisa(request)
        except Exception as e:
            # Solo el tipo: el mensaje puede llevar la dirección (OWASP A09)
            logger.error("Session closed notice failed in the background: %s", type(e).__name__)
