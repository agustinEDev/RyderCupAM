"""
Caso de Uso: Refrescar con la RFEG el hándicap de quien juega hoy (BE #502).

Lo lanza el vigilante cada 15 minutos. Decidido con Agustín el 7 oct 2026: a las
3:00 hora del campo de cada día de juego, a quien juega ese día y todavía no ha
empezado, en todas las competiciones. La RFEG publica hacia las 0:00-0:30, y un
jugador puede haber jugado otro torneo la víspera.

Cómo, para no molestar a nadie a esas horas:

- **Uno a uno y con pausa** entre consultas, cada uno en su propia transacción:
  un fallo con un jugador no deshace a los demás.
- **Cada resultado se apunta**: así ninguna vuelta repite lo hecho, aunque el
  servidor se reinicie, y solo se reintenta lo que falló (hasta las 7:00).
- Quien juega **dos torneos** el mismo día se pregunta una vez, y el resultado
  se apunta en los dos.

Sin zona horaria del campo no se sabe qué hora es allí, así que esa sesión no
se refresca: el mismo criterio que la apertura sola de la anotación.
"""

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.application.services.refresco_rfeg import RefrescoRfeg
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    Candidato,
    RefrescoDeHandicapsService,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)

# Segundos entre una consulta a la RFEG y la siguiente
PAUSA_ENTRE_CONSULTAS = 2.0

UnidadDeTrabajo = Callable[[], tuple[CompetitionUnitOfWorkInterface, UserRepositoryInterface]]


class RefrescarHandicapsDelDiaUseCase:
    """Una vuelta del vigilante: refresca a quien toque en este momento."""

    def __init__(
        self,
        unidad_de_trabajo: UnidadDeTrabajo,
        handicap_service: HandicapService | None,
        timezone: ICompetitionTimezone,
        reloj: Callable[[], datetime],
        esperar: Callable[[float], Awaitable[None]],
    ):
        """
        Args:
            unidad_de_trabajo: Da una unidad de trabajo de competición y el
                repositorio de usuarios de su misma sesión, nuevos cada vez
            handicap_service: La RFEG
            timezone: Dice en qué huso está el campo de cada sesión
            reloj: La hora actual, con huso
            esperar: La pausa entre consultas
        """
        self._unidad_de_trabajo = unidad_de_trabajo
        self._handicap_service = handicap_service
        self._timezone = timezone
        self._reloj = reloj
        self._esperar = esperar

    async def execute(self) -> int:
        """
        Returns:
            A cuántos jugadores se ha preguntado en esta vuelta
        """
        ahora = self._reloj()
        pendientes = await self._pendientes(ahora)

        for numero, (user_id, donde) in enumerate(pendientes.items()):
            if numero:
                await self._esperar(PAUSA_ENTRE_CONSULTAS)
            await self._refrescar(user_id, donde, ahora)
        return len(pendientes)

    async def _pendientes(self, ahora: datetime) -> dict[UserId, list[tuple[CompetitionId, date]]]:
        """A quién preguntar, y en qué torneos y días apuntar lo que salga."""
        pendientes: dict[UserId, list[tuple[CompetitionId, date]]] = defaultdict(list)
        uow, _ = self._unidad_de_trabajo()
        async with uow:
            # Ayer, hoy y mañana en UTC cubren el «hoy» de cualquier huso
            dias = {ahora.date() + timedelta(days=d) for d in (-1, 0, 1)}
            sesiones: dict[tuple[CompetitionId, date], list[Round]] = defaultdict(list)
            for sesion in await uow.rounds.find_by_dates(dias):
                sesiones[(sesion.competition_id, sesion.round_date)].append(sesion)

            for (competition_id, dia), del_dia in sesiones.items():
                ahora_local = await self._hora_local(del_dia[0], ahora)
                if ahora_local is None or not RefrescoDeHandicapsService.toca(ahora_local, dia):
                    continue
                competicion = await uow.competitions.find_by_id(competition_id)
                if competicion is None or competicion.status.is_final():
                    continue
                candidatos = await self._candidatos(uow, competition_id, del_dia)
                resultados = await uow.handicap_refreshes.del_dia(competition_id, dia)
                for user_id in RefrescoDeHandicapsService.a_quien(
                    candidatos, resultados, ahora_local
                ):
                    pendientes[user_id].append((competition_id, dia))
        return pendientes

    async def _hora_local(self, sesion: Round, ahora: datetime) -> datetime | None:
        zona = await self._timezone.for_course(sesion.golf_course_id)
        if zona is None:
            return None
        try:
            return ahora.astimezone(ZoneInfo(zona))
        except (ZoneInfoNotFoundError, ValueError):
            logger.warning("Zona horaria desconocida en un campo: %s", zona)
            return None

    @staticmethod
    async def _candidatos(
        uow: CompetitionUnitOfWorkInterface,
        competition_id: CompetitionId,
        sesiones_del_dia: list[Round],
    ) -> list[Candidato]:
        """
        Quien juega ese día: los de sus partidos, y todos los inscritos mientras
        alguna sesión de ese día no tenga aún los partidos generados.
        """
        inscritos = {
            e.user_id: e
            for e in await uow.enrollments.find_by_competition_and_status(
                competition_id, EnrollmentStatus.APPROVED
            )
        }
        juegan: dict[UserId, bool] = {}
        falta_alguna = False
        for sesion in sesiones_del_dia:
            partidos = await uow.matches.find_by_round(sesion.id)
            falta_alguna = falta_alguna or not partidos
            for partido in partidos:
                empezado = partido.status is not MatchStatus.SCHEDULED
                for jugador in (*partido.team_a_players, *partido.team_b_players):
                    juegan[jugador.user_id] = juegan.get(jugador.user_id, False) or empezado
        if falta_alguna:
            for user_id in inscritos:
                juegan.setdefault(user_id, False)

        return [
            Candidato(
                user_id=user_id,
                handicap_personalizado=user_id in inscritos
                and inscritos[user_id].has_custom_handicap(),
                empezo_hoy=empezo,
            )
            for user_id, empezo in juegan.items()
        ]

    async def _refrescar(
        self, user_id: UserId, donde: list[tuple[CompetitionId, date]], ahora: datetime
    ) -> None:
        """Pregunta por un jugador y lo apunta en cada torneo, en su propia transacción."""
        uow, usuarios = self._unidad_de_trabajo()
        try:
            async with uow:
                jugador = await usuarios.find_by_id(user_id)
                if jugador is None:
                    return
                resultado = await RefrescoRfeg(self._handicap_service, usuarios).consultar(jugador)
                for competition_id, dia in donde:
                    await uow.handicap_refreshes.apuntar(
                        competition_id, dia, user_id, resultado, ahora
                    )
        except Exception:
            # Uno que falla no para a los demás: se reintentará en otra vuelta
            logger.exception("No se pudo refrescar el hándicap de %s", user_id)
