"""
TournamentType Value Object - El tipo de torneo de una competición (RyderCupAM#251).

Decidido con el dueño del producto el 1 oct 2026: modalidad → tipo. Cada tipo
pertenece a una sola modalidad, y la competición guarda solo el tipo: la
modalidad se deriva, así que no puede existir un «stroke play + Ryder Cup».

Aquí solo están los tipos que se pueden jugar. Los que vendrán (eliminatoria
individual y por parejas en match play; parejas y scramble en stroke play) los
enseña el frontend como «Próximamente», y se añaden aquí con su implementación.

No confundir con `SetupMode.RYDER_CUP`, que es cómo se montan los partidos de
una Ryder (capitanes, draft y sobres), no qué torneo es.
"""

from enum import StrEnum

from src.shared.domain.value_objects.modality import Modality


class TournamentType(StrEnum):
    """Qué torneo se juega."""

    RYDER_CUP = "RYDER_CUP"
    STABLEFORD = "STABLEFORD"
    MEDAL = "MEDAL"

    @property
    def modality(self) -> Modality:
        """La modalidad a la que pertenece."""
        return _MODALITY[self]

    @property
    def label(self) -> str:
        """Su nombre en los mensajes: «Un Stableford no tiene equipos»."""
        return _LABEL[self]

    @property
    def has_teams(self) -> bool:
        """Si el torneo se juega entre dos equipos, con lo que cuelga de ellos."""
        return self is TournamentType.RYDER_CUP

    def __str__(self) -> str:
        return self.value


_MODALITY: dict[TournamentType, Modality] = {
    TournamentType.RYDER_CUP: Modality.MATCH_PLAY,
    TournamentType.STABLEFORD: Modality.STROKE_PLAY,
    TournamentType.MEDAL: Modality.STROKE_PLAY,
}

_LABEL: dict[TournamentType, str] = {
    TournamentType.RYDER_CUP: "Ryder Cup",
    TournamentType.STABLEFORD: "Stableford",
    TournamentType.MEDAL: "Medal",
}
