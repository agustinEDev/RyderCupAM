"""
EsperasDeLaCompeticion - Rellenar las franjas desde su lista y limpiar las listas (#251).

Decidido con Agustín (#251, 20 sep; y 8 oct 2026):

- Cuando se libera una plaza (alguien suelta, se cambia, se retira, o se
  amplía la franja), se **asigna** sola al primero de la lista que pueda
  cogerla; queda marcada para avisarle en «Requiere tu atención».
- Quien consigue plaza, por la lista o directamente, sale de las listas de ese
  día; y de todas, si con ella llena su cupo de jornadas.
- Solo mientras las inscripciones están abiertas: al cerrar se vacían.

Va dentro de la transacción de quien llama, con la competición ya bloqueada.
"""

from datetime import datetime

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.listas_de_espera import ListasDeEspera
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class EsperasDeLaCompeticion:
    """Las listas de espera de una competición, vistas desde quien libera o coge plaza."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def rellenar(
        self, competicion: Competition, round_id: RoundId, ahora: datetime
    ) -> list[PlazaEnFranja]:
        """
        Da las plazas libres de la franja a los primeros de su lista que puedan.

        Returns:
            Las plazas asignadas (vacío si no toca rellenar)
        """
        if competicion.status is not CompetitionStatus.ACTIVE or competicion.stroke_play is None:
            return []
        franja = await self._uow.rounds.find_by_id(round_id)
        if franja is None or franja.hoja_de_salidas is None:
            return []
        sesiones = {s.id: s for s in await self._uow.rounds.find_by_competition(competicion.id)}
        asignadas: list[PlazaEnFranja] = []
        for espera in await self._uow.esperas.de_la_competicion(competicion.id):
            if espera.round_id != round_id:
                continue
            plazas = await self._uow.plazas.de_la_competicion(competicion.id)
            if sum(1 for p in plazas if p.round_id == round_id) >= franja.hoja_de_salidas.cupo:
                break
            suyas = [sesiones[p.round_id] for p in plazas if p.user_id == espera.user_id]
            maximo = competicion.stroke_play.max_matchdays_per_player
            if not ListasDeEspera.le_toca(franja, suyas, maximo):
                continue
            plaza = PlazaEnFranja.crear(
                competicion.id, round_id, espera.user_id, ahora, desde_espera=True
            )
            await self._uow.plazas.add(plaza)
            await self.tras_coger(competicion, espera.user_id)
            asignadas.append(plaza)
        return asignadas

    async def tras_coger(self, competicion: Competition, user_id: UserId) -> None:
        """
        Con plaza nueva, fuera de las listas de ese día; y de todas, si ya llena su
        cupo de jornadas.
        """
        if competicion.stroke_play is None:
            return
        sesiones = {s.id: s for s in await self._uow.rounds.find_by_competition(competicion.id)}
        plazas = await self._uow.plazas.de_la_competicion(competicion.id)
        juega = {sesiones[p.round_id].round_date for p in plazas if p.user_id == user_id}
        lleno = len(juega) >= competicion.stroke_play.max_matchdays_per_player
        for espera in await self._uow.esperas.de_la_competicion(competicion.id):
            if espera.user_id != user_id:
                continue
            if lleno or sesiones[espera.round_id].round_date in juega:
                await self._uow.esperas.quitar(espera.round_id, user_id)

    async def sacar_de_todas(self, competicion: Competition, user_id: UserId) -> None:
        """Fuera de todas las listas de la competición (al retirarse)."""
        for espera in await self._uow.esperas.de_la_competicion(competicion.id):
            if espera.user_id == user_id:
                await self._uow.esperas.quitar(espera.round_id, user_id)
