"""
QuickMatch Entity (Aggregate Root) - Representa una partida informal entre amigos.

Permite jugar una ronda sin crear un torneo completo. Desacoplada del aggregate
Competition; reutiliza Value Objects y el motor de calculo de scoring del modulo
competition por composicion, no por herencia ni acoplamiento de persistencia.
"""

from datetime import datetime

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.events.domain_event import DomainEvent

from ..events.quick_match_cancelled_event import QuickMatchCancelledEvent
from ..events.quick_match_completed_event import QuickMatchCompletedEvent
from ..events.quick_match_created_event import QuickMatchCreatedEvent
from ..events.quick_match_participant_added_event import QuickMatchParticipantAddedEvent
from ..events.quick_match_participant_removed_event import QuickMatchParticipantRemovedEvent
from ..events.quick_match_started_event import QuickMatchStartedEvent
from ..exceptions.quick_match_violations import (
    CreatorCannotBeRemovedViolation,
    DuplicateParticipantViolation,
    IncompleteRosterViolation,
    InvalidQuickMatchStatusViolation,
    InvalidScorerConfigurationViolation,
    InvalidTeamAssignmentViolation,
    NotQuickMatchParticipantViolation,
    QuickMatchFullViolation,
)
from ..value_objects.participant_id import ParticipantId
from ..value_objects.quick_match_id import QuickMatchId
from ..value_objects.quick_match_participant import QuickMatchParticipant
from ..value_objects.quick_match_status import QuickMatchStatus

MAX_SCORERS = 4
MAX_NAME_LENGTH = 100


class QuickMatch:
    """
    Entidad QuickMatch (Aggregate Root) - Partida rapida entre amigos.

    Gestiona:
    - Alta/baja de participantes (registrados o invitados) mientras esta PENDING
    - Inicio (roster completo + configuracion de anotadores) y finalizacion
    - Invariantes de capacidad por formato (SINGLES 1v1, FOURBALL/FOURSOMES 2v2)

    Invariantes:
    - El participante del creador siempre existe y nunca puede ser eliminado
    - Solo PENDING permite añadir/quitar participantes
    - start() exige el roster exacto del formato y una configuracion de anotadores valida
    - scorer_ids es siempre un subconjunto de participantes registrados que incluye al creador
    """

    def __init__(
        self,
        id: QuickMatchId,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        match_format: MatchFormat,
        status: QuickMatchStatus,
        participants: list[QuickMatchParticipant],
        name: str | None = None,
        scorer_ids: list[ParticipantId] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        domain_events: list[DomainEvent] | None = None,
    ):
        self._id = id
        self._creator_id = creator_id
        self._golf_course_id = golf_course_id
        self._match_format = match_format
        self._status = status
        self._participants = list(participants)
        self._name = self._validate_name(name)
        self._scorer_ids = list(scorer_ids) if scorer_ids else []
        self._created_at = created_at or datetime.now()
        self._updated_at = updated_at or datetime.now()
        self._domain_events: list[DomainEvent] = domain_events or []

    @staticmethod
    def _validate_name(name: str | None) -> str | None:
        """Nombre libre y opcional para diferenciar partidas (sin normalizar mayusculas)."""
        if name is None:
            return None
        trimmed = name.strip()
        if not trimmed:
            return None
        if len(trimmed) > MAX_NAME_LENGTH:
            raise ValueError(f"Quick match name cannot exceed {MAX_NAME_LENGTH} characters.")
        return trimmed

    # ===========================================
    # FACTORY METHODS
    # ===========================================

    @classmethod
    def create(
        cls,
        id: QuickMatchId,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        match_format: MatchFormat,
        name: str | None = None,
    ) -> "QuickMatch":
        """Factory method: crea una partida rapida con el creador como primer participante."""
        now = datetime.now()
        creator_team = None if match_format == MatchFormat.SINGLES else "A"
        creator_participant = QuickMatchParticipant.for_user(creator_id, team=creator_team)

        quick_match = cls(
            id=id,
            creator_id=creator_id,
            golf_course_id=golf_course_id,
            match_format=match_format,
            status=QuickMatchStatus.PENDING,
            participants=[creator_participant],
            name=name,
            created_at=now,
            updated_at=now,
        )

        quick_match.add_domain_event(
            QuickMatchCreatedEvent(
                quick_match_id=str(quick_match._id),
                creator_id=str(creator_id),
                golf_course_id=str(golf_course_id),
                match_format=match_format.value,
            )
        )
        quick_match.add_domain_event(
            QuickMatchParticipantAddedEvent(
                quick_match_id=str(quick_match._id),
                participant_id=str(creator_participant.participant_id),
                team=creator_team,
            )
        )

        return quick_match

    @classmethod
    def reconstruct(
        cls,
        id: QuickMatchId,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        match_format: MatchFormat,
        status: QuickMatchStatus,
        participants: list[QuickMatchParticipant],
        name: str | None = None,
        scorer_ids: list[ParticipantId] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> "QuickMatch":
        """Reconstruye una partida rapida desde la base de datos (sin domain events)."""
        return cls(
            id=id,
            creator_id=creator_id,
            golf_course_id=golf_course_id,
            match_format=match_format,
            status=status,
            participants=participants,
            name=name,
            scorer_ids=scorer_ids,
            created_at=created_at,
            updated_at=updated_at,
        )

    # ===========================================
    # PROPERTIES (Encapsulacion — solo lectura)
    # ===========================================

    @property
    def id(self) -> QuickMatchId:
        return self._id

    @property
    def creator_id(self) -> UserId:
        return self._creator_id

    @property
    def creator_participant_id(self) -> ParticipantId:
        """Derivado de creator_id — no se persiste como columna propia."""
        return ParticipantId(self._creator_id.value)

    @property
    def golf_course_id(self) -> GolfCourseId:
        return self._golf_course_id

    @property
    def match_format(self) -> MatchFormat:
        return self._match_format

    @property
    def name(self) -> str | None:
        return self._name

    @property
    def status(self) -> QuickMatchStatus:
        return self._status

    @property
    def participants(self) -> list[QuickMatchParticipant]:
        return list(self._participants)

    @property
    def scorer_ids(self) -> list[ParticipantId]:
        return list(self._scorer_ids)

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    # ===========================================
    # METODOS DE CONSULTA (QUERIES)
    # ===========================================

    def is_participant(self, participant_id: ParticipantId) -> bool:
        return any(p.participant_id == participant_id for p in self._participants)

    def find_participant(self, participant_id: ParticipantId) -> QuickMatchParticipant | None:
        for p in self._participants:
            if p.participant_id == participant_id:
                return p
        return None

    def is_scorer(self, participant_id: ParticipantId) -> bool:
        return participant_id in self._scorer_ids

    def capacity(self) -> int:
        """Numero total de jugadores requeridos por el formato."""
        return self._match_format.players_per_team() * 2

    def is_roster_complete(self) -> bool:
        return len(self._participants) == self.capacity()

    def registered_participants(self) -> list[QuickMatchParticipant]:
        return [p for p in self._participants if not p.is_guest]

    def _team_count(self, team: str) -> int:
        return sum(1 for p in self._participants if p.team == team)

    # ===========================================
    # METODOS DE COMANDO (CAMBIOS DE ESTADO)
    # ===========================================

    def add_participant(self, participant: QuickMatchParticipant) -> None:
        """Añade un participante (registrado o invitado) mientras la partida esta PENDING."""
        if not self._status.is_pending():
            raise InvalidQuickMatchStatusViolation(
                f"Cannot add participants to a quick match in status {self._status.value}."
            )

        if self.is_participant(participant.participant_id):
            raise DuplicateParticipantViolation(
                f"{participant.participant_id} is already a participant of this quick match."
            )

        if len(self._participants) >= self.capacity():
            raise QuickMatchFullViolation(
                f"Quick match already has the maximum of {self.capacity()} participants."
            )

        team = participant.team
        if self._match_format == MatchFormat.SINGLES:
            if team is not None:
                raise InvalidTeamAssignmentViolation("SINGLES matches do not use teams.")
        else:
            if team not in ("A", "B"):
                raise InvalidTeamAssignmentViolation("team must be 'A' or 'B' for this format.")
            if self._team_count(team) >= self._match_format.players_per_team():
                raise QuickMatchFullViolation(f"Team {team} is already full.")

        now = datetime.now()
        # Reasignar (no `.append()` in-place) para que SQLAlchemy detecte el cambio
        # en la columna JSONB `participants` al hacer flush/commit.
        self._participants = [*self._participants, participant]
        self._updated_at = now

        self.add_domain_event(
            QuickMatchParticipantAddedEvent(
                quick_match_id=str(self._id),
                participant_id=str(participant.participant_id),
                team=team,
            )
        )

    def remove_participant(self, participant_id: ParticipantId) -> None:
        """Elimina un participante mientras la partida esta PENDING."""
        if not self._status.is_pending():
            raise InvalidQuickMatchStatusViolation(
                f"Cannot remove participants from a quick match in status {self._status.value}."
            )

        if participant_id == self.creator_participant_id:
            raise CreatorCannotBeRemovedViolation(
                "The creator cannot be removed; cancel the quick match instead."
            )

        if not self.is_participant(participant_id):
            raise NotQuickMatchParticipantViolation(
                f"{participant_id} is not a participant of this quick match."
            )

        now = datetime.now()
        self._participants = [p for p in self._participants if p.participant_id != participant_id]
        self._updated_at = now

        self.add_domain_event(
            QuickMatchParticipantRemovedEvent(
                quick_match_id=str(self._id), participant_id=str(participant_id)
            )
        )

    def start(self, scorer_ids: list[ParticipantId]) -> None:
        """
        Inicia la partida (PENDING -> IN_PROGRESS).

        Exige el roster completo y una configuracion de anotadores valida:
        - Entre 1 y 4 anotadores.
        - Todos deben ser participantes registrados (no invitados).
        - El creador debe estar siempre incluido.
        - No puede haber mas anotadores que participantes registrados.
        """
        if not self._status.can_transition_to(QuickMatchStatus.IN_PROGRESS):
            raise InvalidQuickMatchStatusViolation(
                f"Cannot start a quick match in status {self._status.value}."
            )

        if not self.is_roster_complete():
            raise IncompleteRosterViolation(
                f"Quick match requires exactly {self.capacity()} participants to start "
                f"({len(self._participants)} currently)."
            )

        self._validate_scorer_ids(scorer_ids)

        now = datetime.now()
        self._status = QuickMatchStatus.IN_PROGRESS
        self._scorer_ids = list(scorer_ids)
        self._updated_at = now

        self.add_domain_event(QuickMatchStartedEvent(quick_match_id=str(self._id)))

    def _validate_scorer_ids(self, scorer_ids: list[ParticipantId]) -> None:
        if not (1 <= len(scorer_ids) <= MAX_SCORERS):
            raise InvalidScorerConfigurationViolation(
                f"scorer_ids must contain between 1 and {MAX_SCORERS} participants."
            )

        if len(set(scorer_ids)) != len(scorer_ids):
            raise InvalidScorerConfigurationViolation("scorer_ids cannot contain duplicates.")

        if self.creator_participant_id not in scorer_ids:
            raise InvalidScorerConfigurationViolation("The creator must always be a scorer.")

        registered_ids = {p.participant_id for p in self.registered_participants()}
        for sid in scorer_ids:
            if sid not in registered_ids:
                raise InvalidScorerConfigurationViolation(
                    f"{sid} is not a registered participant and cannot be a scorer."
                )

    def complete(self) -> None:
        """Finaliza la partida (IN_PROGRESS -> COMPLETED)."""
        if not self._status.can_transition_to(QuickMatchStatus.COMPLETED):
            raise InvalidQuickMatchStatusViolation(
                f"Cannot complete a quick match in status {self._status.value}."
            )

        now = datetime.now()
        self._status = QuickMatchStatus.COMPLETED
        self._updated_at = now

        self.add_domain_event(QuickMatchCompletedEvent(quick_match_id=str(self._id)))

    def cancel(self) -> None:
        """Cancela la partida (PENDING/IN_PROGRESS -> CANCELLED)."""
        if not self._status.can_transition_to(QuickMatchStatus.CANCELLED):
            raise InvalidQuickMatchStatusViolation(
                f"Cannot cancel a quick match in status {self._status.value}."
            )

        now = datetime.now()
        self._status = QuickMatchStatus.CANCELLED
        self._updated_at = now

        self.add_domain_event(QuickMatchCancelledEvent(quick_match_id=str(self._id)))

    # ===========================================
    # DOMAIN EVENTS
    # ===========================================

    def add_domain_event(self, event: DomainEvent) -> None:
        if not hasattr(self, "_domain_events") or self._domain_events is None:
            self._domain_events = []
        self._domain_events.append(event)

    def get_domain_events(self) -> list[DomainEvent]:
        if not hasattr(self, "_domain_events") or self._domain_events is None:
            self._domain_events = []
        return self._domain_events.copy()

    def clear_domain_events(self) -> None:
        self._domain_events = []

    # ===========================================
    # METODOS ESPECIALES
    # ===========================================

    def __str__(self) -> str:
        return f"QuickMatch({self._match_format.value}, {self._status.value})"

    def __eq__(self, other) -> bool:
        return isinstance(other, QuickMatch) and self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)
