"""Caso de Uso: Los avisos de Actividad que salen de una competicion (BE-2)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time

from src.modules.social.application.publication import stamp_for_publication
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.utc_clock import utc_now

# Como los logros de torneo: a mediodia UTC el dia cae en el mismo sitio en
# cualquier zona de -12 a +12
_MEDIODIA_UTC = time(12, 0)

# Los avisos que salen de una competicion: todos menos los logros y la
# partida rapida
_AVISOS_DE_TORNEO = frozenset(
    {
        ActivityEventType.ENROLLMENT_APPROVED,
        ActivityEventType.INVITED_TO_TOURNAMENT,
        ActivityEventType.ENROLLMENT_REQUEST_CLOSED,
        ActivityEventType.ENROLLMENT_REJECTED,
        ActivityEventType.ENROLLED_IN_TOURNAMENT,
        ActivityEventType.TOURNAMENT_MATCH_RESULT,
        ActivityEventType.TOURNAMENT_FINAL_STANDING,
        ActivityEventType.ENROLLMENT_CONFIRMED,
    }
)

# Lo que se retira cuando uno deja de estar inscrito: al retirarse o al
# cancelarse el torneo (B11 y tabla del 22 oct, C)
_DE_INSCRITO = [
    ActivityEventType.ENROLLED_IN_TOURNAMENT,
    ActivityEventType.ENROLLMENT_CONFIRMED,
]

# Lo que dice `Match.result["winner"]`
_EMPATE = "HALVED"


@dataclass(frozen=True)
class TournamentRef:
    """Lo que un aviso cuenta de su torneo; el nombre, como era al publicarse."""

    competition_id: str
    name: str
    start_date: date
    end_date: date
    is_public: bool


@dataclass(frozen=True)
class MatchOutcome:
    """Un partido de match play terminado, con los bandos y lo que dice su resultado."""

    match_id: str
    played_on: date
    team_a: tuple[UserId, ...]
    team_b: tuple[UserId, ...]
    # "A", "B", "HALVED", o None si se cerro sin ningun hoyo validado
    winner: str | None
    # "3&2", "2UP", "AS", "CONCEDED", "W/O"...
    score: str | None


@dataclass(frozen=True)
class StandingRef:
    """La fila de un jugador en la clasificacion oficial, tal cual la da la app."""

    user_id: UserId
    position: int | None
    tied: bool
    value: int | None
    status: str


class PublishCompetitionNoticesUseCase:
    """
    Publica, retira y corrige los avisos que salen de una competicion.

    **No decide nada de la competicion**: cuando se llama, la accion ya esta
    guardada, y lo que recibe —el resultado, la clasificacion— es el oficial.
    Aqui solo se decide que aviso sale, para quien y con que detalle.

    **Idempotente**: cada aviso es uno por (jugador, origen, tipo), la misma
    clave unica de los logros, asi que un reintento no duplica nada. El origen
    (`source_match_id`) es lo que hace unico al aviso: la inscripcion para los
    de solicitud, la invitacion para el de invitado, el torneo para el de
    apuntado y la clasificacion final, el partido para su resultado.

    **El interruptor de publicacion** lo aplica `stamp_for_publication`: con
    la publicacion apagada lo de los amigos se guarda oculto, y encenderla
    despues no lo destapa.
    """

    def __init__(self, social_uow: SocialUnitOfWorkInterface, user_uow: UserUnitOfWorkInterface):
        self._social_uow = social_uow
        self._user_uow = user_uow

    # === Inscripcion ===

    async def enrolled(
        self, user_id: UserId, tournament: TournamentRef, enrollment_id: str, accepted_request: bool
    ) -> None:
        """
        Queda inscrito: «te han aceptado» si fue aprobando su solicitud (A1), y
        «X se ha apuntado» para sus amigos si el torneo es publico (B8, B9).
        Inscrito directamente o aceptando una invitacion no hay nada que
        aceptarle: le llega «ya estas inscrito» (ENROLLMENT_CONFIRMED, tabla del
        22 oct 2026, C), uno por torneo, para retirarlo al irse.
        """
        eventos = []
        if accepted_request:
            eventos.append(
                self._aviso(
                    user_id, ActivityEventType.ENROLLMENT_APPROVED, enrollment_id, tournament
                )
            )
        else:
            eventos.append(
                self._aviso(
                    user_id,
                    ActivityEventType.ENROLLMENT_CONFIRMED,
                    tournament.competition_id,
                    tournament,
                )
            )
        if tournament.is_public:
            eventos.append(
                self._aviso(
                    user_id,
                    ActivityEventType.ENROLLED_IN_TOURNAMENT,
                    tournament.competition_id,
                    tournament,
                )
            )
        await self._publicar(eventos)

    async def left(self, user_id: UserId, competition_id: str) -> None:
        """
        Se retira: sus amigos dejan de ver que esta apuntado (B11) y el deja de
        ver «ya estas inscrito» (C).
        """
        await self._retirar(competition_id, _DE_INSCRITO, user_id)

    async def tournament_cancelled(self, competition_id: str) -> None:
        """Torneo cancelado: nadie esta ya apuntado a el (B11, C)."""
        await self._retirar(competition_id, _DE_INSCRITO)

    async def invited(self, user_id: UserId, tournament: TournamentRef, invitation_id: str) -> None:
        """Le invitan (A3). Uno por invitacion: si se retira, se retira ese."""
        await self._publicar(
            [
                self._aviso(
                    user_id, ActivityEventType.INVITED_TO_TOURNAMENT, invitation_id, tournament
                )
            ]
        )

    async def invitation_withdrawn(self, user_id: UserId, invitation_id: str) -> None:
        """El organizador retira la invitacion: su aviso desaparece (A4)."""
        await self._retirar(invitation_id, [ActivityEventType.INVITED_TO_TOURNAMENT], user_id)

    async def invitation_answered(self, user_id: UserId, invitation_id: str) -> None:
        """
        El invitado la acepta o la rechaza: su aviso de invitado ya no pide nada
        y desaparece (tabla del 22 oct 2026, C).
        """
        await self._retirar(invitation_id, [ActivityEventType.INVITED_TO_TOURNAMENT], user_id)

    async def invitations_closed(self, invitations: Sequence[tuple[UserId, str]]) -> None:
        """
        Invitaciones que se cerraron solas (sin plaza o caducadas): su aviso de
        invitado ya no pide nada y desaparece (Agustin, 22 oct 2026). Todas en
        la misma transaccion.
        """
        if not invitations:
            return
        # Un solo borrado para todo el lote, no uno por invitacion
        async with self._social_uow:
            await self._social_uow.activity_events.delete_pairs(
                ActivityEventType.INVITED_TO_TOURNAMENT, invitations
            )

    async def requests_closed(
        self, tournament: TournamentRef, requests: Sequence[tuple[UserId, str]]
    ) -> None:
        """Solicitudes que se quedaron sin atender al empezar: «se cerro sin plaza» (A5)."""
        await self._publicar(
            [
                self._aviso(
                    user_id, ActivityEventType.ENROLLMENT_REQUEST_CLOSED, enrollment_id, tournament
                )
                for user_id, enrollment_id in requests
            ]
        )

    async def request_rejected(
        self, user_id: UserId, tournament: TournamentRef, enrollment_id: str
    ) -> None:
        """El organizador la rechaza a mano: un aviso distinto del cierre (A6)."""
        await self._publicar(
            [self._aviso(user_id, ActivityEventType.ENROLLMENT_REJECTED, enrollment_id, tournament)]
        )

    # === Resultados ===

    async def match_finished(self, tournament: TournamentRef, match: MatchOutcome) -> None:
        """
        Un aviso por jugador con su lado del resultado (C13): ganado, perdido o
        empatado, el tanteo tal cual («3&2», «CONCEDED», «W/O») y contra quien.

        Sin ganador —cerrado sin un solo hoyo validado— no hay nada que contar.
        """
        if match.winner is None:
            return

        jugado = datetime.combine(match.played_on, _MEDIODIA_UTC)
        eventos = []
        for bando, suyos, rivales in (
            ("A", match.team_a, match.team_b),
            ("B", match.team_b, match.team_a),
        ):
            for user_id in suyos:
                payload = {
                    **self._del_torneo(tournament),
                    "outcome": self._lado(match.winner, bando),
                    "score": match.score,
                    "partner_ids": [str(u.value) for u in suyos if u != user_id],
                    "opponent_ids": [str(u.value) for u in rivales],
                }
                eventos.append(
                    ActivityEvent.create(
                        user_id=user_id,
                        type=ActivityEventType.TOURNAMENT_MATCH_RESULT,
                        occurred_at=jugado,
                        source_match_id=match.match_id,
                        payload=payload,
                    )
                )
        await self._publicar(eventos)

    async def final_standings(
        self, tournament: TournamentRef, tournament_type: str, rows: Sequence[StandingRef]
    ) -> None:
        """
        La clasificacion final de cada inscrito (C14): su puesto en la general
        oficial, de cuantos, si lo comparte y su valor (puntos en Stableford,
        golpes respecto al par en Medal). Quien no tiene puesto (NP, NR) lo
        recibe sin el, con su estado.
        """
        terminado = datetime.combine(tournament.end_date, _MEDIODIA_UTC)
        await self._sustituir(
            tournament.competition_id,
            ActivityEventType.TOURNAMENT_FINAL_STANDING,
            [
                ActivityEvent.create(
                    user_id=fila.user_id,
                    type=ActivityEventType.TOURNAMENT_FINAL_STANDING,
                    occurred_at=terminado,
                    source_match_id=tournament.competition_id,
                    payload={
                        **self._del_torneo(tournament),
                        "tournament_type": tournament_type,
                        "position": fila.position,
                        "tied": fila.tied,
                        "total_players": len(rows),
                        "value": fila.value,
                        "status": fila.status,
                    },
                )
                for fila in rows
            ],
        )

    async def reopened(self, competition_id: str) -> None:
        """
        Se reabre un torneo terminado: su clasificacion final ya no vale (C15).
        Se borra, y al volver a cerrarlo sale la nueva: con la clave unica, la
        vieja impediria publicarla.
        """
        await self._retirar(competition_id, [ActivityEventType.TOURNAMENT_FINAL_STANDING])

    async def tournament_made_private(self, competition_id: str) -> None:
        """
        El torneo deja de ser publico: sus amigos dejan de ver quien se apunto
        (revision de BE-2). Al reves no se publica nada hacia atras.
        """
        await self._retirar(competition_id, [ActivityEventType.ENROLLED_IN_TOURNAMENT])

    async def tournament_deleted(self, competition_id: str) -> None:
        """
        El torneo se borra: fuera todos sus avisos, sea cual sea su origen
        (inscripcion, invitacion, partido o el propio torneo). Se buscan por el
        `competition_id` que lleva cada uno en el `payload`.
        """
        async with self._social_uow:
            await self._social_uow.activity_events.delete_for_competition(
                competition_id, _AVISOS_DE_TORNEO
            )

    # === Ayudas ===

    def _aviso(
        self,
        user_id: UserId,
        tipo: ActivityEventType,
        origen: str,
        tournament: TournamentRef,
    ) -> ActivityEvent:
        return ActivityEvent.create(
            user_id=user_id,
            type=tipo,
            occurred_at=utc_now(),
            source_match_id=origen,
            payload=self._del_torneo(tournament),
        )

    @staticmethod
    def _del_torneo(tournament: TournamentRef) -> dict:
        return {
            "competition_id": tournament.competition_id,
            "competition_name": tournament.name,
            "start_date": tournament.start_date.isoformat(),
            "end_date": tournament.end_date.isoformat(),
        }

    @staticmethod
    def _lado(winner: str, bando: str) -> str:
        if winner == _EMPATE:
            return "HALVED"
        return "WON" if winner == bando else "LOST"

    async def _publicar(self, eventos: list[ActivityEvent]) -> None:
        if not eventos:
            return
        # Una fecha para todos y el interruptor de cada uno, de ahora mismo
        eventos = await stamp_for_publication(self._user_uow, eventos)
        async with self._social_uow:
            await self._social_uow.activity_events.add_many(eventos)

    async def _sustituir(
        self, origen: str, tipo: ActivityEventType, eventos: list[ActivityEvent]
    ) -> None:
        """
        Borra lo publicado de ese tipo desde ese origen y publica lo nuevo, en
        la misma transaccion: si el borrado al reabrir fallo, la clasificacion
        vieja no puede impedir la nueva (con la clave unica, el alta se la
        saltaria) ni quedar a medias.
        """
        eventos = await stamp_for_publication(self._user_uow, eventos)
        async with self._social_uow:
            await self._social_uow.activity_events.delete_from_source(origen, [tipo])
            await self._social_uow.activity_events.add_many(eventos)

    async def _retirar(
        self, origen: str, tipos: list[ActivityEventType], user_id: UserId | None = None
    ) -> None:
        async with self._social_uow:
            await self._social_uow.activity_events.delete_from_source(origen, tipos, user_id)
