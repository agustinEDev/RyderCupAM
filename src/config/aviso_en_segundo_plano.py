"""
El aviso de «nuevo inicio de sesión», en segundo plano (BE #737).

El login contesta sin esperar al proveedor de correo: el aviso se lanza como una
tarea del propio proceso, con su propia sesión de BD, porque la de la petición se
cierra al contestar. Si el proceso se reinicia justo entonces, ese correo se pierde
(decidido así: el login no espera).
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.modules.user.application.dto.device_dto import AvisoDeNuevoInicioRequestDTO
from src.modules.user.application.ports.aviso_de_nuevo_inicio_port import IAvisoDeNuevoInicio
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.services.aviso_de_nuevo_inicio_de_sesion import (
    AvisoDeNuevoInicioDeSesion,
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


async def espera_los_avisos_pendientes() -> None:
    """Espera a los avisos en marcha (para los tests)."""
    while _PENDIENTES:
        await asyncio.gather(*list(_PENDIENTES), return_exceptions=True)


class AvisoEnSegundoPlano(IAvisoDeNuevoInicio):
    """Lanza el aviso sin que el login lo espere."""

    def __init__(self, fabrica: async_sessionmaker[AsyncSession], email_service: IEmailService):
        self._fabrica = fabrica
        self._email_service = email_service

    async def avisa(self, request: AvisoDeNuevoInicioRequestDTO) -> None:
        """Lanza el aviso y vuelve enseguida. Si no toca avisar, ni lo lanza."""
        if not request.toca_avisar():
            return
        tarea = asyncio.create_task(self._avisa(request))
        _PENDIENTES.add(tarea)
        tarea.add_done_callback(_PENDIENTES.discard)

    async def _avisa(self, request: AvisoDeNuevoInicioRequestDTO) -> None:
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
