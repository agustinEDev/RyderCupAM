"""
Caso de Uso: Una vuelta del vigilante de las actualizaciones de hándicaps (#251).

Decidido con Agustín el 7 oct 2026: nada se refresca solo de forma periódica;
el vigilante está para dos cosas y nada más:

- **Lanzar las programadas** que llegan a su hora, como si el organizador
  pulsara el botón: termina la última si quedó a medias, o empieza otra. Si a
  esa hora la ventana está cerrada, no se lanza y se le avisa con el motivo.
- **Recuperar las cortadas por un reinicio**: la pasada corre en una tarea del
  proceso, y si el servidor se reinicia se queda «en curso» para siempre. Sin
  actividad en `SIN_ACTIVIDAD`, se da por terminada: incompleta si falta alguien
  (y se avisa, para que la termine con el botón) o completa si no.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from src.modules.competition.application.exceptions import ActualizacionEnCursoError
from src.modules.competition.application.ports.handicap_update_email_service_interface import (
    IHandicapUpdateEmailService,
)
from src.modules.competition.application.ports.lanzador_de_actualizaciones import (
    LanzadorDeActualizaciones,
)
from src.modules.competition.application.services.actualizaciones_de_handicaps import (
    ActualizacionesDeHandicaps,
)
from src.modules.competition.application.services.avisos_al_organizador import (
    AvisosAlOrganizador,
)
from src.modules.competition.application.services.pendientes_de_actualizar import (
    PendientesDeActualizar,
)
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.application.services.ventana_de_la_competicion import ventana_de
from src.modules.competition.application.use_cases.refrescar_handicaps_use_case import (
    FabricaDeHerramientas,
)
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    OrigenActualizacion,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId

logger = logging.getLogger(__name__)

# Una pasada apunta a alguien cada pocos segundos (como mucho ~42 s por jugador
# con la RFEG lenta): 10 minutos sin nada es que ya no corre
SIN_ACTIVIDAD = timedelta(minutes=10)


class VigilarActualizacionesUseCase:
    """Una vuelta: lanza las programadas vencidas y recupera las cortadas."""

    def __init__(
        self,
        herramientas: FabricaDeHerramientas,
        lanzador: LanzadorDeActualizaciones,
        avisos: IHandicapUpdateEmailService | None,
        reloj: Callable[[], datetime],
    ):
        self._herramientas = herramientas
        self._lanzador = lanzador
        self._avisos = AvisosAlOrganizador(avisos)
        self._reloj = reloj

    async def execute(self) -> int:
        """
        Returns:
            Cuántas programadas y cortadas se han atendido en esta vuelta
        """
        ahora = self._reloj()
        async with self._herramientas() as h, h.competiciones as uow:
            vencidas = await uow.handicap_updates.programadas_vencidas(ahora)
            cortadas = await uow.handicap_updates.en_curso_sin_actividad_desde(
                ahora - SIN_ACTIVIDAD
            )
        for competition_id in vencidas:
            await self._con_cuidado(self._programada, competition_id, ahora)
        for actualizacion in cortadas:
            await self._con_cuidado(self._cortada, actualizacion, ahora)
        return len(vencidas) + len(cortadas)

    async def _con_cuidado(self, accion, sobre, ahora: datetime) -> None:
        """Una que falla no impide atender a las demás."""
        try:
            await accion(sobre, ahora)
        except Exception:
            logger.exception("El vigilante no pudo atender %s", sobre)

    async def _programada(self, competition_id: CompetitionId, ahora: datetime) -> None:
        lanzada: ActualizacionDeHandicaps | None = None
        motivo: str | None = None
        organizador = None
        async with self._herramientas() as h, h.competiciones as uow:
            competicion = await uow.competitions.find_by_id_for_update(competition_id)
            # Se quita siempre: se lance o no, ya llegó su hora
            await uow.handicap_updates.anular_programada(competition_id)
            if competicion is None:
                return
            actualizaciones = ActualizacionesDeHandicaps(uow, self._lanzador)
            ventana = await ventana_de(uow, h.zonas, competicion, ahora)
            if ventana.abierta:
                try:
                    lanzada, _ = await actualizaciones.a_mano(
                        competition_id, OrigenActualizacion.PROGRAMADA, ahora
                    )
                except ActualizacionEnCursoError:
                    # Ya hay una en marcha (el botón, o el cierre): eso ya lo hace
                    return
            else:
                motivo = ventana.motivo
                organizador = await self._avisos.quien(h.usuarios, competicion)
        if lanzada is not None:
            # Ya guardada: la pasada la encuentra
            self._lanzador.lanzar(lanzada.id)
        elif motivo is not None:
            await self._avisos.no_lanzada(organizador, competicion, motivo)

    async def _cortada(self, actualizacion: ActualizacionDeHandicaps, ahora: datetime) -> None:
        nombres: list[str] = []
        organizador = None
        async with self._herramientas() as h, h.competiciones as uow:
            competicion = await uow.competitions.find_by_id_for_update(actualizacion.competition_id)
            actual = await uow.handicap_updates.find_by_id(actualizacion.id)
            if competicion is None or actual is None or not actual.sigue():
                return
            pendientes = await PendientesDeActualizar.de(uow, actual)
            actual.terminar(len(pendientes), ahora)
            await uow.handicap_updates.update(actual)
            if pendientes:
                por_id = await PlayerNames.de_la_competicion(
                    pendientes, competicion.id, h.usuarios, uow
                )
                nombres = list(por_id.values())
                organizador = await self._avisos.quien(h.usuarios, competicion)
        if nombres:
            await self._avisos.pendientes(organizador, competicion, nombres)
