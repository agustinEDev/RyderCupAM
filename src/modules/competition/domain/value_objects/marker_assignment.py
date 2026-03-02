"""
MarkerAssignment Value Object - Asignacion de marcador para scoring.

Define quien marca a quien en un partido. Es inmutable.
"""

from dataclasses import dataclass

from src.modules.user.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class MarkerAssignment:
    """
    Value Object que define la relacion de marcaje entre jugadores.

    Atributos:
        scorer_user_id: El jugador que registra scores
        marks_user_id: El jugador al que este scorer marca (registra su score)
        marked_by_user_id: El jugador que marca al scorer (registra el score del scorer)
    """

    scorer_user_id: UserId
    marks_user_id: UserId
    marked_by_user_id: UserId

    def __post_init__(self):
        """Validaciones de integridad."""
        if self.scorer_user_id == self.marks_user_id:
            raise ValueError("Un jugador no puede marcarse a si mismo")
        if self.scorer_user_id == self.marked_by_user_id:
            raise ValueError("Un jugador no puede ser marcado por si mismo")
