"""
MatchPlayer Value Object - Jugador dentro de un partido con handicap calculado.

NO es una entidad (no tiene identidad propia), es un Value Object embebido en Match.
"""

from dataclasses import dataclass

from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId

MAX_HOLES = 18


@dataclass(frozen=True)
class MatchPlayer:
    """
    Value Object que representa un jugador dentro de un partido.

    Contiene la información calculada del jugador para ese partido específico:
    - Su ID de usuario
    - El handicap de juego calculado (Playing Handicap)
    - La categoría de tee que usa
    - Los hoyos donde recibe golpes

    Características:
    - Inmutable (frozen dataclass)
    - Se compara por valor (todos los atributos)
    - No tiene identidad propia (vive dentro de Match)

    Ejemplo:
        >>> player = MatchPlayer(
        ...     user_id=UserId.generate(),
        ...     playing_handicap=12,
        ...     tee_category=TeeCategory.AMATEUR_MALE,
        ...     strokes_received=[1, 3, 5, 7, 9, 11, 13, 15, 17, 2, 4, 6]
        ... )
    """

    user_id: UserId
    playing_handicap: int
    tee_category: TeeCategory
    strokes_received: tuple[int, ...]  # Hoyos donde recibe golpe (inmutable)

    def __post_init__(self):
        """Validaciones después de inicialización."""
        if self.playing_handicap < 0:
            raise ValueError(f"playing_handicap must be >= 0, got {self.playing_handicap}")

        # Validar que strokes_received son números de hoyo válidos (1-18)
        for hole in self.strokes_received:
            if not 1 <= hole <= MAX_HOLES:
                raise ValueError(f"Invalid hole number in strokes_received: {hole}")

        # Validar que no hay hoyos duplicados
        if len(self.strokes_received) != len(set(self.strokes_received)):
            raise ValueError("Duplicate hole numbers in strokes_received")

    @classmethod
    def create(
        cls,
        user_id: UserId,
        playing_handicap: int,
        tee_category: TeeCategory,
        strokes_received: list[int] | tuple[int, ...],
    ) -> "MatchPlayer":
        """
        Factory method para crear un MatchPlayer.

        Args:
            user_id: ID del jugador
            playing_handicap: Handicap de juego calculado
            tee_category: Categoría de tee que usa
            strokes_received: Lista de hoyos donde recibe golpe

        Returns:
            Nueva instancia de MatchPlayer
        """
        return cls(
            user_id=user_id,
            playing_handicap=playing_handicap,
            tee_category=tee_category,
            strokes_received=tuple(strokes_received),
        )

    def receives_stroke_on_hole(self, hole_number: int) -> bool:
        """
        Verifica si el jugador recibe golpe en un hoyo específico.

        Args:
            hole_number: Número de hoyo (1-18)

        Returns:
            True si recibe golpe en ese hoyo
        """
        return hole_number in self.strokes_received

    def __repr__(self) -> str:
        return (
            f"MatchPlayer(user_id={self.user_id}, "
            f"playing_handicap={self.playing_handicap}, "
            f"strokes={len(self.strokes_received)})"
        )
