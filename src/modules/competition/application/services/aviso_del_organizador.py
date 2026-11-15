"""
El aviso de Actividad del organizador, siempre al día (R4, revisión del 16 nov 2026).

«{N} jugadores sin actualizar con la RFEG en X» lo ponen al día la pasada al
terminar y el jugador al que la RFEG encuentra desde su perfil. Si cada uno
calculara el número en su transacción y lo publicara después, dos a la vez
podrían publicar en desorden y dejar el número viejo.

Por eso se lee y se publica **con la competición bloqueada** (`FOR UPDATE`),
dentro de la misma transacción: quien publica después ha esperado al anterior
y lee lo último, así que el último publicado es siempre el de verdad. La
transacción solo lee y bloquea; Actividad escribe en su propia sesión.
"""

import logging

from src.modules.competition.application.services.avisos_de_actividad import (
    AvisosDeActividad,
    FabricaDeActividad,
)
from src.modules.competition.application.services.fijado_de_la_rfeg import (
    FabricaDeHerramientas,
)
from src.modules.competition.application.services.sin_actualizar_de_la_competicion import (
    SinActualizarDeLaCompeticion,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus

logger = logging.getLogger(__name__)


async def poner_al_dia_el_del_organizador(
    herramientas: FabricaDeHerramientas,
    actividad: FabricaDeActividad,
    competition_id: CompetitionId,
) -> None:
    """
    Con la competición bloqueada, cuántos quedan sin actualizar, y su aviso: con
    ese número, o retirado si no queda nadie (D3). Solo en una cerrada con la
    última actualización terminada (H1). Un fallo se queda en el log.
    """
    try:
        async with herramientas() as h, h.competiciones as uow:
            competicion = await uow.competitions.find_by_id_for_update(competition_id)
            if competicion is None or competicion.status is not CompetitionStatus.CLOSED:
                return
            actualizacion = await uow.handicap_updates.ultima_de(competition_id)
            if actualizacion is None or not SinActualizarDeLaCompeticion.terminada(actualizacion):
                return
            hecho = await SinActualizarDeLaCompeticion.de(
                uow, h.usuarios, competicion, actualizacion
            )
            async with actividad() as publicador:
                avisos = AvisosDeActividad(publicador)
                if hecho.para_el_organizador:
                    await avisos.handicaps_not_updated(competicion, len(hecho.para_el_organizador))
                else:
                    await avisos.handicaps_not_updated_withdrawn(competicion)
    except Exception:
        logger.warning(
            "Could not update the organiser's RFEG notice of %s",
            competition_id.value,
            exc_info=True,
        )
