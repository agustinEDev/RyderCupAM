"""
QuickMatch Entity (Aggregate Root) - Representa una partida informal entre amigos.

Permite jugar una ronda sin crear un torneo completo. Desacoplada del aggregate
Competition; reutiliza Value Objects y el motor de calculo de scoring del modulo
competition por composicion, no por herencia ni acoplamiento de persistencia.
"""

from datetime import datetime

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.events.domain_event import DomainEvent
from src.shared.domain.value_objects.gender import Gender

from ..events.quick_match_cancelled_event import QuickMatchCancelledEvent
from ..events.quick_match_completed_event import QuickMatchCompletedEvent
from ..events.quick_match_created_event import QuickMatchCreatedEvent
from ..events.quick_match_hidden_event import QuickMatchHiddenEvent
from ..events.quick_match_participant_added_event import QuickMatchParticipantAddedEvent
from ..events.quick_match_participant_handicap_updated_event import (
    QuickMatchParticipantHandicapUpdatedEvent,
)
from ..events.quick_match_participant_removed_event import QuickMatchParticipantRemovedEvent
from ..events.quick_match_started_event import QuickMatchStartedEvent
from ..events.quick_match_unhidden_event import QuickMatchUnhiddenEvent
from ..exceptions.quick_match_violations import (
    CreatorCannotBeRemovedViolation,
    DuplicateParticipantViolation,
    IncompleteRosterViolation,
    InvalidAllowanceViolation,
    InvalidQuickMatchFormatViolation,
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
from ..value_objects.scoring_format import ScoringFormat

MAX_SCORERS = 4
MAX_NAME_LENGTH = 100
MAX_FREE_PLAY_PLAYERS = 4

# WHS allowance defaults (%), igual que Round.get_effective_allowance() en `competition`
# para los formatos por equipos; FREE_PLAY_ALLOWANCE es el estandar WHS de Stroke Play.
ALLOWED_ALLOWANCE_PERCENTAGES = frozenset(range(50, 101, 5))  # {50, 55, ..., 100}
SINGLES_ALLOWANCE = 100
FOURBALL_ALLOWANCE = 90
FOURSOMES_ALLOWANCE = 50
FREE_PLAY_ALLOWANCE = 95


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
        match_format: MatchFormat | None,
        status: QuickMatchStatus,
        participants: list[QuickMatchParticipant],
        name: str | None = None,
        scoring_format: ScoringFormat | None = None,
        allowance_percentage: int | None = None,
        play_mode: PlayMode = PlayMode.HANDICAP,
        scorer_ids: list[ParticipantId] | None = None,
        hidden_by_participant_ids: list[ParticipantId] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        domain_events: list[DomainEvent] | None = None,
    ):
        self._validate_format(match_format, scoring_format)
        self._validate_allowance(allowance_percentage)
        self._id = id
        self._creator_id = creator_id
        self._golf_course_id = golf_course_id
        self._match_format = match_format
        self._scoring_format = scoring_format
        self._allowance_percentage = allowance_percentage
        self._play_mode = play_mode
        self._status = status
        self._participants = list(participants)
        self._name = self._validate_name(name)
        self._scorer_ids = list(scorer_ids) if scorer_ids else []
        self._hidden_by_participant_ids = (
            list(hidden_by_participant_ids) if hidden_by_participant_ids else []
        )
        self._created_at = created_at or datetime.now()
        self._updated_at = updated_at or datetime.now()
        self._domain_events: list[DomainEvent] = domain_events or []

    @staticmethod
    def _validate_format(
        match_format: MatchFormat | None, scoring_format: ScoringFormat | None
    ) -> None:
        """Exige exactamente uno de match_format (Ryder Cup) o scoring_format (partido libre)."""
        if (match_format is None) == (scoring_format is None):
            raise InvalidQuickMatchFormatViolation(
                "Exactly one of match_format or scoring_format must be provided."
            )

    @staticmethod
    def _validate_allowance(allowance_percentage: int | None) -> None:
        """Si se personaliza, debe ser 50-100 en incrementos de 5 (igual que Round)."""
        if (
            allowance_percentage is not None
            and allowance_percentage not in ALLOWED_ALLOWANCE_PERCENTAGES
        ):
            raise InvalidAllowanceViolation(
                f"allowance_percentage must be one of {sorted(ALLOWED_ALLOWANCE_PERCENTAGES)}, "
                f"got {allowance_percentage}."
            )

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
        match_format: MatchFormat | None = None,
        scoring_format: ScoringFormat | None = None,
        name: str | None = None,
        allowance_percentage: int | None = None,
        play_mode: PlayMode = PlayMode.HANDICAP,
        creator_tee_color: TeeColor | None = None,
        creator_tee_gender: Gender | None = None,
    ) -> "QuickMatch":
        """
        Factory method: crea una partida rapida con el creador como primer participante.

        Exactamente uno de match_format (Ryder Cup, por equipos) o scoring_format
        (partido libre, todos contra todos) debe indicarse. allowance_percentage
        personalizado debe ser 50-100 en incrementos de 5; si se omite, se usa el
        default WHS del formato (ver get_effective_allowance()).

        play_mode decide si se aplican handicaps: SCRATCH juega a golpes brutos
        (nadie recibe golpes, en cualquier formato) y HANDICAP —el default— aplica
        el reparto WHS. Es el mismo Value Object que usa `Competition.play_mode`.
        """
        now = datetime.now()
        uses_teams = match_format is not None and match_format != MatchFormat.SINGLES
        creator_team = "A" if uses_teams else None
        creator_participant = QuickMatchParticipant.for_user(
            creator_id,
            team=creator_team,
            tee_color=creator_tee_color,
            tee_gender=creator_tee_gender,
        )

        quick_match = cls(
            id=id,
            creator_id=creator_id,
            golf_course_id=golf_course_id,
            match_format=match_format,
            scoring_format=scoring_format,
            allowance_percentage=allowance_percentage,
            play_mode=play_mode,
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
                match_format=match_format.value if match_format else None,
                scoring_format=scoring_format.value if scoring_format else None,
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
        match_format: MatchFormat | None,
        status: QuickMatchStatus,
        participants: list[QuickMatchParticipant],
        name: str | None = None,
        scoring_format: ScoringFormat | None = None,
        allowance_percentage: int | None = None,
        play_mode: PlayMode = PlayMode.HANDICAP,
        scorer_ids: list[ParticipantId] | None = None,
        hidden_by_participant_ids: list[ParticipantId] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> "QuickMatch":
        """Reconstruye una partida rapida desde la base de datos (sin domain events)."""
        return cls(
            id=id,
            creator_id=creator_id,
            golf_course_id=golf_course_id,
            match_format=match_format,
            scoring_format=scoring_format,
            allowance_percentage=allowance_percentage,
            play_mode=play_mode,
            status=status,
            participants=participants,
            name=name,
            scorer_ids=scorer_ids,
            hidden_by_participant_ids=hidden_by_participant_ids,
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
    def match_format(self) -> MatchFormat | None:
        return self._match_format

    @property
    def scoring_format(self) -> ScoringFormat | None:
        return self._scoring_format

    @property
    def allowance_percentage(self) -> int | None:
        """Allowance personalizado (50-100); None si se usa el default WHS del formato."""
        return self._allowance_percentage

    @property
    def play_mode(self) -> PlayMode:
        """SCRATCH (golpes brutos) o HANDICAP (reparto WHS). Default HANDICAP."""
        return self._play_mode

    def uses_handicap(self) -> bool:
        """
        Si esta partida reparte golpes de handicap.

        Se consulta desde el reparto de golpes y desde el calculo del resultado,
        que son dos sitios distintos: una partida SCRATCH no debe pintar puntos en
        la tarjeta *ni* restar nada al bruto.
        """
        return self._play_mode.allows_handicap()

    def get_effective_allowance(self) -> int:
        """
        Porcentaje de allowance efectivo para el Playing Handicap.

        Si se configuro un allowance_percentage personalizado, lo retorna. Si no,
        el default WHS: SINGLES 100% (match play), FOURBALL 90%, FOURSOMES 50%,
        partido libre (MEDAL/STABLEFORD, stroke play) 95%.
        """
        if self._allowance_percentage is not None:
            return self._allowance_percentage

        if self._match_format == MatchFormat.SINGLES:
            return SINGLES_ALLOWANCE
        if self._match_format == MatchFormat.FOURBALL:
            return FOURBALL_ALLOWANCE
        if self._match_format == MatchFormat.FOURSOMES:
            return FOURSOMES_ALLOWANCE
        return FREE_PLAY_ALLOWANCE

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
    def hidden_by_participant_ids(self) -> list[ParticipantId]:
        """Participantes que han ocultado esta partida de su propio historial."""
        return list(self._hidden_by_participant_ids)

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

    def is_hidden_for(self, participant_id: ParticipantId) -> bool:
        return participant_id in self._hidden_by_participant_ids

    def capacity(self) -> int:
        """Numero maximo de jugadores admitidos por el formato."""
        if self._match_format is not None:
            return self._match_format.players_per_team() * 2
        return MAX_FREE_PLAY_PLAYERS

    def is_roster_complete(self) -> bool:
        """
        Match play (Ryder Cup): exige el roster exacto de la capacidad del formato.
        Partido libre: cualquier roster es valido para empezar (1 a 4, incluido solo
        el creador), no hace falta llenar hasta el maximo.
        """
        if self._match_format is not None:
            return len(self._participants) == self.capacity()
        return True

    def registered_participants(self) -> list[QuickMatchParticipant]:
        return [p for p in self._participants if not p.is_guest]

    def team_rosters(self) -> tuple[set[ParticipantId], set[ParticipantId]] | None:
        """
        Deriva los dos bandos (A y B) de participantes para el calculo de standing.

        Reutiliza la misma convencion de asignacion de equipo que `add_participant()`:
        en formatos que usan equipos (FOURBALL/FOURSOMES), el campo `team` de cada
        participante decide el bando. En SINGLES (que no usa el campo `team`, ver
        `add_participant`) los dos unicos participantes son cada bando por convencion.

        Devuelve `None` si no hay exactamente dos bandos no vacios resolubles (por
        ejemplo, con menos de 2 participantes, o un FOURBALL/FOURSOMES incompleto
        con ambos participantes aun en el mismo equipo).
        """
        if self._match_format == MatchFormat.SINGLES:
            if len(self._participants) != 2:  # noqa: PLR2004
                return None
            return (
                {self._participants[0].participant_id},
                {self._participants[1].participant_id},
            )

        if self._match_format is None:
            return None

        team_a_ids = {p.participant_id for p in self._participants if p.team == "A"}
        team_b_ids = {p.participant_id for p in self._participants if p.team == "B"}

        if not team_a_ids or not team_b_ids:
            return None

        return team_a_ids, team_b_ids

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
        uses_teams = self._match_format is not None and self._match_format != MatchFormat.SINGLES
        if not uses_teams:
            if team is not None:
                raise InvalidTeamAssignmentViolation("This quick match format does not use teams.")
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

    def set_participant_handicap(
        self, participant_id: ParticipantId, handicap: float | None
    ) -> None:
        """
        Edita el handicap de un participante mientras la partida esta PENDING.

        Manual (`handicap`) para invitados, override (`custom_handicap`) para
        registrados — pensado para el resumen previo a `start()`, donde el creador
        puede ajustar el handicap de quien no tenga uno en su perfil.
        """
        if not self._status.is_pending():
            raise InvalidQuickMatchStatusViolation(
                f"Cannot edit participant handicap in status {self._status.value}."
            )

        participant = self.find_participant(participant_id)
        if participant is None:
            raise NotQuickMatchParticipantViolation(
                f"{participant_id} is not a participant of this quick match."
            )

        updated_participant = participant.with_handicap(handicap)
        now = datetime.now()
        self._participants = [
            updated_participant if p.participant_id == participant_id else p
            for p in self._participants
        ]
        self._updated_at = now

        self.add_domain_event(
            QuickMatchParticipantHandicapUpdatedEvent(
                quick_match_id=str(self._id),
                participant_id=str(participant_id),
                handicap=handicap,
            )
        )

    def hide_for(self, participant_id: ParticipantId) -> None:
        """
        Oculta la partida del historial personal de un participante.

        No requiere ningun estado concreto de la partida (a diferencia de
        add/remove_participant): un participante puede ocultar una partida
        PENDING, IN_PROGRESS, COMPLETED o CANCELLED por igual. No afecta al
        resto de participantes ni borra ningun dato — es puramente personal.
        Idempotente: ocultar dos veces no es un error.
        """
        if not self.is_participant(participant_id):
            raise NotQuickMatchParticipantViolation(
                f"{participant_id} is not a participant of this quick match."
            )

        if participant_id in self._hidden_by_participant_ids:
            return

        self._hidden_by_participant_ids = [*self._hidden_by_participant_ids, participant_id]
        self._updated_at = datetime.now()

        self.add_domain_event(
            QuickMatchHiddenEvent(quick_match_id=str(self._id), participant_id=str(participant_id))
        )

    def unhide_for(self, participant_id: ParticipantId) -> None:
        """Vuelve a mostrar la partida en el historial personal de un participante. Idempotente."""
        if not self.is_participant(participant_id):
            raise NotQuickMatchParticipantViolation(
                f"{participant_id} is not a participant of this quick match."
            )

        if participant_id not in self._hidden_by_participant_ids:
            return

        self._hidden_by_participant_ids = [
            pid for pid in self._hidden_by_participant_ids if pid != participant_id
        ]
        self._updated_at = datetime.now()

        self.add_domain_event(
            QuickMatchUnhiddenEvent(
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
        format_value = (
            self._match_format.value if self._match_format else self._scoring_format.value
        )
        return f"QuickMatch({format_value}, {self._status.value})"

    def __eq__(self, other) -> bool:
        return isinstance(other, QuickMatch) and self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)
