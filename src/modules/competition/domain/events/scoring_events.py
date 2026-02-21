"""Scoring Domain Events - Eventos relacionados con el scoring de partidos."""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class HoleScoreSubmittedEvent(DomainEvent):
    """Evento emitido cuando se registra un score en un hoyo."""

    match_id: str
    hole_number: int
    scorer_user_id: str


@dataclass(frozen=True)
class ScorecardSubmittedEvent(DomainEvent):
    """Evento emitido cuando un jugador entrega su tarjeta."""

    match_id: str
    user_id: str
    all_submitted: bool


@dataclass(frozen=True)
class MatchConcededEvent(DomainEvent):
    """Evento emitido cuando un equipo concede el partido."""

    match_id: str
    conceding_team: str
    reason: str | None
