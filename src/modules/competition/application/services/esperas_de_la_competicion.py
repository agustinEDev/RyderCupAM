"""
EsperasDeLaCompeticion - Rellenar las franjas desde su lista y limpiar las listas (#251).

Decidido con Agustín (#251, 20 sep; y 8 oct 2026):

- Cuando se libera una plaza (alguien suelta, se cambia, se retira, se amplía
  la franja o sube el cupo de jornadas), se **asigna** sola al primero de la
  lista que pueda cogerla; queda marcada para avisarle en «Requiere tu atención».
- Quien consigue plaza, por la lista o directamente, sale de las listas de ese
  día; y de todas, si con ella llena su cupo de jornadas. Lo mismo si cambia
  qué días juega porque se mueve una franja.
- Solo mientras las inscripciones están abiertas, y nunca en una franja que ya
  se está jugando o se jugó (tras volver atrás).

Va dentro de la transacción de quien llama, con la competición ya bloqueada.
Lee sesiones, plazas y esperas una vez por llamada.
"""

from datetime import datetime

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.espera_en_franja import EsperaEnFranja
from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.listas_de_espera import ListasDeEspera
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.user.domain.value_objects.user_id import UserId

# Una franja en juego o jugada no admite esperas ni asignaciones
JUGADA = {RoundStatus.IN_PROGRESS, RoundStatus.COMPLETED}


def esta_jugada(franja: Round) -> bool:
    """Si la franja ya se está jugando o se jugó."""
    return franja.status in JUGADA


class _Foto:
    """Sesiones, plazas y esperas de la competición, leídas una vez y al día."""

    def __init__(
        self,
        sesiones: dict[RoundId, Round],
        plazas: list[PlazaEnFranja],
        esperas: list[EsperaEnFranja],
    ):
        self.sesiones = sesiones
        self.plazas = plazas
        self.esperas = esperas

    def suyas(self, user_id: UserId) -> list[Round]:
        return [self.sesiones[p.round_id] for p in self.plazas if p.user_id == user_id]

    def ocupadas(self, round_id: RoundId) -> int:
        return sum(1 for p in self.plazas if p.round_id == round_id)


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
        if not self._rellena(competicion):
            return []
        foto = await self._foto(competicion)
        return await self._rellenar(competicion, foto, round_id, ahora)

    async def rellenar_todas(self, competicion: Competition, ahora: datetime) -> None:
        """Cada franja, por si ahora puede entrar alguien a quien antes se saltó."""
        if not self._rellena(competicion):
            return
        foto = await self._foto(competicion)
        for round_id in list(foto.sesiones):
            await self._rellenar(competicion, foto, round_id, ahora)

    async def tras_coger(self, competicion: Competition, user_id: UserId) -> None:
        """
        Con plaza nueva, fuera de las listas de ese día; y de todas, si ya llena su
        cupo de jornadas.
        """
        if competicion.stroke_play is None:
            return
        await self._limpiar(competicion, await self._foto(competicion), {user_id})

    async def limpiar(self, competicion: Competition) -> None:
        """
        Las listas de todos, al día de qué juega cada uno: tras mover una franja de
        día o cambiar el cupo de jornadas.
        """
        if competicion.stroke_play is None:
            return
        foto = await self._foto(competicion)
        await self._limpiar(competicion, foto, {e.user_id for e in foto.esperas})

    async def sacar_de_todas(self, competicion: Competition, user_id: UserId) -> None:
        """Fuera de todas las listas de la competición (al retirarse)."""
        for espera in await self._uow.esperas.de_la_competicion(competicion.id):
            if espera.user_id == user_id:
                await self._uow.esperas.quitar(espera.round_id, user_id)

    @staticmethod
    def _rellena(competicion: Competition) -> bool:
        return (
            competicion.status is CompetitionStatus.ACTIVE and competicion.stroke_play is not None
        )

    @staticmethod
    def _maximo(competicion: Competition) -> int:
        """El cupo de jornadas por jugador (en una Ryder no hay listas: cero)."""
        return competicion.stroke_play.max_matchdays_per_player if competicion.stroke_play else 0

    async def _foto(self, competicion: Competition) -> _Foto:
        return _Foto(
            {s.id: s for s in await self._uow.rounds.find_by_competition(competicion.id)},
            await self._uow.plazas.de_la_competicion(competicion.id),
            await self._uow.esperas.de_la_competicion(competicion.id),
        )

    async def _rellenar(
        self, competicion: Competition, foto: _Foto, round_id: RoundId, ahora: datetime
    ) -> list[PlazaEnFranja]:
        franja = foto.sesiones.get(round_id)
        if franja is None or franja.hoja_de_salidas is None or esta_jugada(franja):
            return []
        maximo = self._maximo(competicion)
        asignadas: list[PlazaEnFranja] = []
        for espera in [e for e in foto.esperas if e.round_id == round_id]:
            if foto.ocupadas(round_id) >= franja.hoja_de_salidas.cupo:
                break
            if espera not in foto.esperas:
                continue
            if not ListasDeEspera.le_toca(franja, foto.suyas(espera.user_id), maximo):
                continue
            plaza = PlazaEnFranja.crear(
                competicion.id, round_id, espera.user_id, ahora, desde_espera=True
            )
            await self._uow.plazas.add(plaza)
            foto.plazas.append(plaza)
            await self._limpiar(competicion, foto, {espera.user_id})
            asignadas.append(plaza)
        return asignadas

    async def _limpiar(self, competicion: Competition, foto: _Foto, quienes: set[UserId]) -> None:
        maximo = self._maximo(competicion)
        for espera in list(foto.esperas):
            if espera.user_id not in quienes:
                continue
            juega = {s.round_date for s in foto.suyas(espera.user_id)}
            if len(juega) >= maximo or foto.sesiones[espera.round_id].round_date in juega:
                await self._uow.esperas.quitar(espera.round_id, espera.user_id)
                foto.esperas.remove(espera)
