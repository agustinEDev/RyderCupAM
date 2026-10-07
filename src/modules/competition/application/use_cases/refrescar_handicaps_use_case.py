"""
Caso de Uso: Una pasada de una actualización de hándicaps con la RFEG (#251).

Decidido con Agustín el 7 oct 2026, como hace la RFEG («el hándicap de la base
de datos tras el cierre de inscripción»). Sustituye al refresco de las 3:00 de
cada día de juego (BE #502). Al cerrar las inscripciones se crea una
actualización y se lanza esta pasada en segundo plano.

- **En un Stableford o un Medal** todavía cerrado, si la RFEG da otro
  hándicap, se corrige el fijado y se rehacen las categorías.
- **En la Ryder** solo cambia el perfil: los partidos salen de él.
- Si alguien se queda sin actualizar, la actualización queda **incompleta** y
  se avisa al organizador por correo. Una pasada sobre una incompleta termina
  solo lo que falta.
- Si la competición empieza a mitad, la actualización se corta y la pasada
  para: lo pendiente se queda como estaba.

Cómo:

- **Uno a uno y con pausa**, con hasta 3 intentos por jugador, cada uno con
  sus propias herramientas (sesión nueva): un fallo con un jugador no arrastra
  a los demás.
- **La RFEG se consulta sin ninguna transacción abierta**: puede tardar hasta
  10 s, y mientras tanto no tiene sentido tener una conexión ocupada.
- **Todo queda apuntado**, también lo que falla de forma inesperada.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.modules.competition.application.ports.handicap_update_email_service_interface import (
    IHandicapUpdateEmailService,
)
from src.modules.competition.application.services.handicaps_al_cerrar import HandicapsAlCerrar
from src.modules.competition.application.services.pendientes_de_actualizar import (
    PendientesDeActualizar,
)
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.application.services.refresco_rfeg import RefrescoRfeg
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    MAX_INTENTOS,
    ResultadoRefresco,
)
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)

# Segundos entre un jugador y el siguiente, y entre un intento fallido y el siguiente
PAUSA_ENTRE_JUGADORES = 2.0
PAUSA_ENTRE_INTENTOS = 5.0


@dataclass(frozen=True)
class Herramientas:
    """
    Lo que hace falta para una parte de la pasada, sobre una misma sesión.

    La competición y los usuarios TIENEN que compartir sesión: el hándicap nuevo
    del perfil se guarda con los usuarios y se confirma al cerrar la unidad de
    trabajo de la competición. Con sesiones distintas se perdería sin error
    (CodeRabbit en la #507).
    """

    competiciones: CompetitionUnitOfWorkInterface
    usuarios: UserRepositoryInterface


# Da herramientas nuevas cada vez, y las cierra al salir
FabricaDeHerramientas = Callable[[], AbstractAsyncContextManager[Herramientas]]


class RefrescarHandicapsUseCase:
    """Una pasada de una actualización: pregunta por quien falte y la termina."""

    def __init__(
        self,
        herramientas: FabricaDeHerramientas,
        handicap_service: HandicapService | None,
        avisos: IHandicapUpdateEmailService | None,
        reloj: Callable[[], datetime],
        esperar: Callable[[float], Awaitable[None]],
    ):
        """
        Args:
            herramientas: Da herramientas nuevas (competición y usuarios sobre
                una misma sesión) cada vez que se le piden
            handicap_service: La RFEG
            avisos: El correo al organizador si queda alguien sin actualizar
            reloj: La hora actual, con huso
            esperar: Las pausas
        """
        self._herramientas = herramientas
        self._handicap_service = handicap_service
        self._avisos = avisos
        self._reloj = reloj
        self._esperar = esperar

    async def execute(self, update_id: uuid.UUID) -> int:
        """
        Returns:
            A cuántos jugadores se ha preguntado en esta pasada
        """
        pendientes = await self._pendientes(update_id)
        preguntados = 0
        for user_id in pendientes:
            if preguntados:
                await self._esperar(PAUSA_ENTRE_JUGADORES)
            if not await self._sigue(update_id):
                return preguntados
            await self._refrescar(update_id, user_id)
            preguntados += 1
        await self._terminar(update_id)
        return preguntados

    async def _pendientes(self, update_id: uuid.UUID) -> list[UserId]:
        """A quién preguntar: los inscritos sin personalizado que no tienen respuesta."""
        async with self._herramientas() as h, h.competiciones as uow:
            actualizacion = await uow.handicap_updates.find_by_id(update_id)
            if actualizacion is None or not actualizacion.sigue():
                return []
            return await PendientesDeActualizar.de(uow, actualizacion)

    async def _sigue(self, update_id: uuid.UUID) -> bool:
        async with self._herramientas() as h, h.competiciones as uow:
            actualizacion = await uow.handicap_updates.find_by_id(update_id)
            return actualizacion is not None and actualizacion.sigue()

    async def _refrescar(self, update_id: uuid.UUID, user_id: UserId) -> None:
        """Hasta 3 intentos con un jugador, con pausa entre uno y otro, mientras siga."""
        for intento in range(MAX_INTENTOS):
            if intento:
                await self._esperar(PAUSA_ENTRE_INTENTOS)
                if not await self._sigue(update_id):
                    return
            if await self._una_vez(update_id, user_id) is not ResultadoRefresco.FALLIDO:
                return

    async def _una_vez(self, update_id: uuid.UUID, user_id: UserId) -> ResultadoRefresco:
        """
        Pregunta por un jugador y lo apunta.

        En tres pasos para no tener la transacción abierta mientras la RFEG
        contesta: leer al jugador, preguntar, y apuntar (que es cuando se
        guarda también su hándicap nuevo y se corrige el fijado).
        """
        try:
            async with self._herramientas() as h:
                async with h.competiciones:
                    jugador = await h.usuarios.find_by_id(user_id)
                if jugador is None:
                    # Ya no existe: no hay a quién preguntar, ni ahora ni luego
                    resultado = ResultadoRefresco.NO_ENCONTRADO
                else:
                    resultado = await RefrescoRfeg(self._handicap_service, h.usuarios).consultar(
                        jugador
                    )
                async with h.competiciones as uow:
                    if (
                        resultado is ResultadoRefresco.ACTUALIZADO
                        and jugador is not None
                        and jugador.handicap is not None
                    ):
                        nuevo = Decimal(str(jugador.handicap.value))
                        await self._corregir(uow, h.usuarios, update_id, user_id, nuevo)
                    await uow.handicap_updates.apuntar(update_id, user_id, resultado, self._reloj())
            return resultado
        except Exception:
            logger.exception("No se pudo refrescar el hándicap de %s", user_id)
            await self._apuntar_el_fallo(update_id, user_id)
            return ResultadoRefresco.FALLIDO

    @staticmethod
    async def _corregir(
        uow: CompetitionUnitOfWorkInterface,
        usuarios: UserRepositoryInterface,
        update_id: uuid.UUID,
        user_id: UserId,
        nuevo: Decimal,
    ) -> None:
        """
        En un stroke play que siga cerrado, el hándicap fijado pasa a ser el nuevo.

        Con la competición bloqueada, y solo si la actualización sigue: si a la
        vez alguien la inicia, una de las dos espera a la otra.
        """
        actualizacion = await uow.handicap_updates.find_by_id(update_id)
        if actualizacion is None:
            return
        competicion = await uow.competitions.find_by_id_for_update(actualizacion.competition_id)
        actualizacion = await uow.handicap_updates.find_by_id(update_id)
        if competicion is not None and actualizacion is not None and actualizacion.sigue():
            await HandicapsAlCerrar(uow, usuarios).corregir(competicion, user_id, nuevo)

    async def _apuntar_el_fallo(self, update_id: uuid.UUID, user_id: UserId) -> None:
        """Un fallo inesperado también se apunta, con herramientas limpias."""
        try:
            async with self._herramientas() as h, h.competiciones as uow:
                await uow.handicap_updates.apuntar(
                    update_id, user_id, ResultadoRefresco.FALLIDO, self._reloj()
                )
        except Exception:
            logger.exception("Tampoco se pudo apuntar el fallo de %s", user_id)

    async def _terminar(self, update_id: uuid.UUID) -> None:
        """
        Completa, o incompleta si alguien se quedó sin actualizar; y entonces se
        avisa al organizador, ya fuera de la transacción.
        """
        async with self._herramientas() as h, h.competiciones as uow:
            actualizacion = await uow.handicap_updates.find_by_id(update_id)
            if actualizacion is None:
                return
            competicion = await uow.competitions.find_by_id_for_update(actualizacion.competition_id)
            actualizacion = await uow.handicap_updates.find_by_id(update_id)
            if competicion is None or actualizacion is None or not actualizacion.sigue():
                return
            sin_actualizar = await PendientesDeActualizar.de(uow, actualizacion)
            actualizacion.terminar(len(sin_actualizar), self._reloj())
            await uow.handicap_updates.update(actualizacion)
            if not sin_actualizar:
                return
            nombres = await PlayerNames.de_la_competicion(
                sin_actualizar, competicion.id, h.usuarios, uow
            )
            organizador = await h.usuarios.find_by_id(competicion.creator_id)
        await self._avisar(organizador, str(competicion.name), str(competicion.id.value), nombres)

    async def _avisar(self, organizador, competicion: str, competition_id: str, nombres) -> None:
        if self._avisos is None or organizador is None or organizador.email is None:
            return
        try:
            await self._avisos.send_handicaps_pending_email(
                to_email=organizador.email.value,
                organizer_name=organizador.get_full_name(),
                competition_name=competicion,
                competition_id=competition_id,
                pending_names=list(nombres.values()),
            )
        except Exception:
            logger.exception("No se pudo avisar al organizador de %s", competition_id)
