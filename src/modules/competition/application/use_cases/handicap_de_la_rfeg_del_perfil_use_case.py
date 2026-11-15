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
  Solo si estaba en la lista (R3): a quien entra cada día y ya estaba al día no
  se le publica nada. Con la primera pasada aún en curso, lo del organizador
  lo dirá la pasada. Si Actividad falla, lo guardado se queda.
- **Una transacción corta por competición** (R1): solo las cerradas, leídas
  de la base, y bloqueadas en orden de id; si una falla, las demás se hacen.
- Lo corre el proceso de la API en segundo plano (R6): quien lo pide desde
  su perfil no espera a los bloqueos.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from src.modules.competition.application.services.aviso_del_organizador import (
    poner_al_dia_el_del_organizador,
)
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
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
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
        avisados: list[Competition] = []
        en_la_lista: list[CompetitionId] = []
        # Una transacción corta por competición, en orden de id: dos a la vez
        # bloquean en el mismo orden, y si una falla las demás se hacen (R1)
        for competition_id in await self._cerradas(user_id):
            try:
                cambio = await self._en_una(competition_id, user_id, handicap)
            except Exception:
                logger.exception(
                    "Could not bring the RFEG handicap of %s to %s",
                    user_id,
                    competition_id.value,
                )
                continue
            if cambio is None:
                continue
            competicion, era_no_encontrado, estaba_en_la_lista = cambio
            if era_no_encontrado:
                avisados.append(competicion)
            if estaba_en_la_lista:
                en_la_lista.append(competition_id)
        await self._en_actividad(user_id, avisados, en_la_lista)

    async def _cerradas(self, user_id: UserId) -> list[CompetitionId]:
        """Las cerradas en las que juega, filtradas en la base y en orden de id; sin bloquear."""
        async with self._herramientas() as h, h.competiciones as uow:
            suyas = [
                i.competition_id
                for i in await uow.enrollments.find_by_user(user_id)
                if i.status == EnrollmentStatus.APPROVED
            ]
            if not suyas:
                return []
            return await uow.competitions.find_ids_with_status(suyas, CompetitionStatus.CLOSED)

    async def _en_una(
        self, competition_id: CompetitionId, user_id: UserId, handicap: Decimal
    ) -> tuple[Competition, bool, bool] | None:
        """
        En una competición, bloqueada como en la pasada: se apunta y se corrige.

        Returns:
            La competición, si era un no encontrado y si estaba en la lista del
            organizador (con la actualización terminada), o None si ya no toca
        """
        async with self._herramientas() as h, h.competiciones as uow:
            competicion = await uow.competitions.find_by_id_for_update(competition_id)
            if competicion is None or competicion.status is not CompetitionStatus.CLOSED:
                return None
            inscripcion = await uow.enrollments.find_by_user_and_competition(
                user_id, competition_id
            )
            if inscripcion is None or inscripcion.status != EnrollmentStatus.APPROVED:
                return None
            ahora = self._reloj()
            era_no_encontrado = estaba_en_la_lista = False
            actualizacion = await uow.handicap_updates.ultima_de(competition_id)
            if actualizacion is not None:
                # Lo de antes: solo si él estaba, cambia algo en Actividad (R3)
                if SinActualizarDeLaCompeticion.terminada(actualizacion):
                    antes = await SinActualizarDeLaCompeticion.de(
                        uow, h.usuarios, competicion, actualizacion
                    )
                    era_no_encontrado = user_id in antes.no_encontrados
                    estaba_en_la_lista = user_id in antes.para_el_organizador
                await uow.handicap_updates.apuntar(
                    actualizacion.id, user_id, ResultadoRefresco.ACTUALIZADO, ahora
                )
            if (await ventana_de(uow, h.zonas, competicion, ahora)).abierta:
                await corregir_el_fijado(uow, h, competicion, user_id, handicap, ahora)
        return competicion, era_no_encontrado, estaba_en_la_lista

    async def _en_actividad(
        self, user_id: UserId, avisados: list[Competition], en_la_lista: list[CompetitionId]
    ) -> None:
        """
        Se le retira su aviso donde lo tenía, y el del organizador se pone al día
        con la competición bloqueada (R4). Un fallo se queda en el log.
        """
        if self._actividad is None:
            return
        if avisados:
            try:
                async with self._actividad() as publicador:
                    actividad = AvisosDeActividad(publicador)
                    for competicion in avisados:
                        await actividad.handicap_not_found_withdrawn(competicion, [user_id])
            except Exception:
                logger.warning("Could not withdraw the RFEG notices of %s", user_id, exc_info=True)
        for competition_id in en_la_lista:
            await poner_al_dia_el_del_organizador(
                self._herramientas, self._actividad, competition_id
            )
