"""
Caso de Uso: Entregar el sobre de un capitan (FE #655).

Cada capitan entrega una lista ORDENADA de los suyos sin ver la del otro, y los
enfrentamientos salen de cruzar las dos por posicion. Se puede corregir hasta
que se abren; despues no, que seria rehacer el sorteo a escondidas.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from src.modules.competition.application.dto.envelope_dto import EnvelopeDTO, envelope_to_dto
from src.modules.competition.application.exceptions import RoundNotFoundError
from src.modules.competition.application.services.envelope_desk import (
    EnvelopeDesk,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class NotATeamCaptainError(Exception):
    """Solo los capitanes entregan sobre."""

    pass


class SubmitEnvelopeUseCase:
    """Caso de uso para entregar —o corregir— el sobre de un equipo."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repository,
        clock=None,
        timezone_service=None,
        generador=None,
    ):
        """
        Args:
            uow: Unit of Work del modulo
            user_repository: Lo pide la mesa de sobres para los handicaps
            clock: El reloj del servidor, para saber si el plazo ya venció
            timezone_service: La zona del campo. Sin ella el plazo no existe y
                solo se abren los sobres a mano
            generador: Crea los partidos si esta entrega es la que los abre
                —los dos pidieron no esperar— (BE #361)
        """
        self._uow = uow
        self._desk = EnvelopeDesk(uow, user_repository, clock, timezone_service, generador)

    async def execute(
        self,
        round_id: UUID,
        user_id: UserId,
        entries: Sequence[Sequence[str | UUID]],
        sin_esperar: bool = False,
    ) -> EnvelopeDTO:
        """
        Guarda la lista del capitan para esa sesion.

        Args:
            round_id: La sesion
            user_id: Quien entrega. De aqui sale el equipo: pedirlo en el
                cuerpo dejaria entregar el sobre del rival
            entries: Las filas, en orden
            sin_esperar: Si este capitan pide abrirlos en cuanto esten los dos,
                sin aguardar a la hora. Hacen falta los DOS para que valga

        Returns:
            El sobre tal como queda

        Raises:
            RoundNotFoundError: Si la sesion no existe
            NotATeamCaptainError: Si quien entrega no capitanea ningun equipo
            EnvelopeAlreadyRevealedError: Si ya se abrio
            PlayerNotInTeamError: Si alguien no es de su equipo
            TeamNotFullyEnteredError: Si falta alguien del equipo
        """
        async with self._uow:
            # Con la competicion bloqueada: dos peticiones a la vez leerian
            # que no hay sobre, las dos lo crearian, y una reventaria contra la
            # clave unica con un 500
            ronda, competition = await self._desk.ronda_y_competicion(
                RoundId(round_id), bloquear=True
            )
            self._desk.comprobar_que_la_sesion_admite_sobres(ronda)
            team = self._desk.equipo_de(competition, user_id)
            if team is None:
                raise NotATeamCaptainError("Solo los capitanes entregan su sobre")

            # El plazo se mira ANTES de aceptar: si ya venció, los sobres se
            # abren y la entrega llega tarde. Si no, entregar después de la
            # hora colaba mientras nadie abriera la pantalla
            sobres_de_la_sesion = {
                s.team: s for s in await self._uow.envelopes.find_by_round(ronda.id)
            }
            await self._desk.revelar_si_toca(ronda, competition, sobres_de_la_sesion)

            sobre = await self._desk.sobre_de(ronda, team, crear=True)
            if sobre is None:  # `crear=True` siempre devuelve uno; esto es para el tipo
                raise RoundNotFoundError("No se pudo preparar el sobre de esta sesión")
            jugadores = await self._desk.jugadores_de(competition, team)
            sobre.submit(
                [[UserId(UUID(str(uid))) for uid in fila] for fila in entries],
                equipo=jugadores,
                por=user_id,
                ahora=datetime.now(UTC).replace(tzinfo=None),
                sin_esperar=sin_esperar,
            )
            await self._uow.envelopes.update(sobre)
            # Y despues: si los dos pidieron no esperar, el segundo en entregar
            # dispara la apertura
            sobres_de_la_sesion[team] = sobre
            await self._desk.revelar_si_toca(ronda, competition, sobres_de_la_sesion)
            return envelope_to_dto(sobre)
