"""
Caso de Uso: La RFEG da el hándicap de un jugador desde su perfil (D1 y D4, 16 nov 2026).

Decidido con Agustín el 16 nov 2026. Cuando el jugador pide su hándicap a la
RFEG desde su perfil (o al entrar) y la RFEG lo da, en cada competición cerrada
y sin empezar en la que juega:

- **Queda apuntado como actualizado con la RFEG** en la última actualización
  (D1): deja de salir como no encontrado, para él y para el organizador. Un
  hándicap puesto a mano no pasa por aquí.
- **En un stroke play, su hándicap fijado pasa a ser el nuevo** y se rehacen
  las categorías, exactamente como en la pasada (D4): con la competición
  bloqueada, solo dentro de la ventana y nunca a quien tiene personalizado.
- **Sus avisos, al momento** (D3): se le retira el de no encontrado y el del
  organizador se pone al día (otro número, o se retira si ya no queda nadie).
  Con la primera pasada aún en curso, lo del organizador lo dirá la pasada.
  Actividad se monta después, fuera de la transacción: si falla, lo guardado
  se queda.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from src.modules.competition.application.services.avisos_de_actividad import (
    AvisosDeActividad,
    FabricaDeActividad,
)
from src.modules.competition.application.services.fijado_de_la_rfeg import (
    FabricaDeHerramientas,
    corregir_el_fijado,
)
from src.modules.competition.application.services.sin_actualizar_de_la_competicion import (
    SinActualizarDeLaCompeticion,
)
from src.modules.competition.application.services.ventana_de_la_competicion import ventana_de
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    ResultadoRefresco,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class HandicapDeLaRfegDelPerfilUseCase:
    """Lleva a sus competiciones cerradas el hándicap que acaba de dar la RFEG."""

    def __init__(
        self,
        herramientas: FabricaDeHerramientas,
        reloj: Callable[[], datetime],
        actividad: FabricaDeActividad | None = None,
    ):
        """
        Args:
            herramientas: Competición y usuarios sobre una misma sesión
            reloj: La hora actual, con huso
            actividad: Monta Actividad para poner al día los avisos (D3)
        """
        self._herramientas = herramientas
        self._reloj = reloj
        self._actividad = actividad

    async def execute(self, user_id: UserId, handicap: Decimal) -> None:
        """
        Args:
            user_id: El jugador
            handicap: Lo que dio la RFEG, ya guardado en su perfil
        """
        # Por competición: None si no hay que tocar el del organizador, o cuántos quedan
        al_dia: list[tuple[Competition, int | None]] = []
        async with self._herramientas() as h, h.competiciones as uow:
            for inscripcion in await uow.enrollments.find_by_user(user_id):
                if inscripcion.status != EnrollmentStatus.APPROVED:
                    continue
                # Bloqueada, como en la pasada: si a la vez alguien la inicia o la
                # pasa, una espera a la otra
                competicion = await uow.competitions.find_by_id_for_update(
                    inscripcion.competition_id
                )
                if competicion is None or competicion.status is not CompetitionStatus.CLOSED:
                    continue
                ahora = self._reloj()
                actualizacion = await uow.handicap_updates.ultima_de(competicion.id)
                if actualizacion is not None:
                    await uow.handicap_updates.apuntar(
                        actualizacion.id, user_id, ResultadoRefresco.ACTUALIZADO, ahora
                    )
                    cuantos = None
                    if SinActualizarDeLaCompeticion.terminada(actualizacion):
                        hecho = await SinActualizarDeLaCompeticion.de(
                            uow, h.usuarios, competicion, actualizacion
                        )
                        cuantos = len(hecho.para_el_organizador)
                    al_dia.append((competicion, cuantos))
                if (await ventana_de(uow, h.zonas, competicion, ahora)).abierta:
                    await corregir_el_fijado(uow, h, competicion, user_id, handicap, ahora)
        await self._en_actividad(user_id, al_dia)

    async def _en_actividad(
        self, user_id: UserId, al_dia: list[tuple[Competition, int | None]]
    ) -> None:
        """Se retira el suyo y el del organizador se pone al día (D3); un fallo, al log."""
        if self._actividad is None or not al_dia:
            return
        try:
            async with self._actividad() as publicador:
                actividad = AvisosDeActividad(publicador)
                for competicion, cuantos in al_dia:
                    await actividad.handicap_not_found_withdrawn(competicion, [user_id])
                    if cuantos is None:
                        continue
                    if cuantos:
                        await actividad.handicaps_not_updated(competicion, cuantos)
                    else:
                        await actividad.handicaps_not_updated_withdrawn(competicion)
        except Exception:
            logger.warning("Could not update the RFEG notices of %s", user_id, exc_info=True)
