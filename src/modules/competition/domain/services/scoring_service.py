"""
ScoringService - Lo que la competición Ryder añade al match play.

- Asignacion de marcadores (quién marca a quién)
- Calculo de puntos Ryder Cup

Las reglas del match play (ganador por hoyo, standing, partido decidido,
resultado) viven en `shared` (`MatchPlayScoring`, RyderCupAM#165) y esta clase
las hereda: las usan también la partida rápida y las estadísticas.
"""

from src.modules.competition.domain.value_objects.marker_assignment import (
    MarkerAssignment,
)
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.match_play_scoring import MatchPlayScoring
from src.shared.domain.value_objects.match_format import MatchFormat


class ScoringService(MatchPlayScoring):
    """
    Servicio de dominio para logica de scoring.

    Es puro (sin dependencias de framework ni IO).
    Se inyecta en use cases via DI.
    """

    def generate_marker_assignments(
        self,
        team_a_players: tuple[MatchPlayer, ...],
        team_b_players: tuple[MatchPlayer, ...],
        match_format: MatchFormat,
    ) -> list[MarkerAssignment]:
        """
        Genera asignaciones de marcadores segun el formato del partido.

        Regla inviolable: el marcador siempre es del equipo contrario.

        - SINGLES: Reciproco (A marca B, B marca A)
        - FOURBALL: Cruzado (A1→B1, A2→B2, B1→A1, B2→A2)
        - FOURSOMES: Uno por equipo del equipo contrario
        """
        if match_format == MatchFormat.SINGLES:
            return self._singles_assignments(team_a_players, team_b_players)
        if match_format == MatchFormat.FOURBALL:
            return self._fourball_assignments(team_a_players, team_b_players)
        # FOURSOMES
        return self._foursomes_assignments(team_a_players, team_b_players)

    def _singles_assignments(
        self,
        team_a: tuple[MatchPlayer, ...],
        team_b: tuple[MatchPlayer, ...],
    ) -> list[MarkerAssignment]:
        """SINGLES: A marca a B, B es marcado por A (reciproco)."""
        a = team_a[0]
        b = team_b[0]
        return [
            MarkerAssignment(
                scorer_user_id=a.user_id,
                marks_user_id=b.user_id,
                marked_by_user_id=b.user_id,
            ),
            MarkerAssignment(
                scorer_user_id=b.user_id,
                marks_user_id=a.user_id,
                marked_by_user_id=a.user_id,
            ),
        ]

    def _fourball_assignments(
        self,
        team_a: tuple[MatchPlayer, ...],
        team_b: tuple[MatchPlayer, ...],
    ) -> list[MarkerAssignment]:
        """FOURBALL: Distributed cross-team. A1→B1, B2→A1, A2→B2, B1→A2."""
        a1, a2 = team_a[0], team_a[1]
        b1, b2 = team_b[0], team_b[1]
        return [
            MarkerAssignment(
                scorer_user_id=a1.user_id, marks_user_id=b1.user_id, marked_by_user_id=b2.user_id
            ),
            MarkerAssignment(
                scorer_user_id=a2.user_id, marks_user_id=b2.user_id, marked_by_user_id=b1.user_id
            ),
            MarkerAssignment(
                scorer_user_id=b1.user_id, marks_user_id=a2.user_id, marked_by_user_id=a1.user_id
            ),
            MarkerAssignment(
                scorer_user_id=b2.user_id, marks_user_id=a1.user_id, marked_by_user_id=a2.user_id
            ),
        ]

    def _foursomes_assignments(
        self,
        team_a: tuple[MatchPlayer, ...],
        team_b: tuple[MatchPlayer, ...],
    ) -> list[MarkerAssignment]:
        """FOURSOMES: Distributed cross-team (same as fourball)."""
        a1, a2 = team_a[0], team_a[1]
        b1, b2 = team_b[0], team_b[1]
        return [
            MarkerAssignment(
                scorer_user_id=a1.user_id, marks_user_id=b1.user_id, marked_by_user_id=b2.user_id
            ),
            MarkerAssignment(
                scorer_user_id=a2.user_id, marks_user_id=b2.user_id, marked_by_user_id=b1.user_id
            ),
            MarkerAssignment(
                scorer_user_id=b1.user_id, marks_user_id=a2.user_id, marked_by_user_id=a1.user_id
            ),
            MarkerAssignment(
                scorer_user_id=b2.user_id, marks_user_id=a1.user_id, marked_by_user_id=a2.user_id
            ),
        ]

    def get_affected_player_ids(
        self,
        team_a_players: tuple[MatchPlayer, ...],
        team_b_players: tuple[MatchPlayer, ...],
        scorer_user_id: UserId,
        match_format: MatchFormat,
    ) -> list[UserId]:
        """
        Retorna los IDs de jugadores cuyos HoleScores se actualizan al enviar own_score.

        - SINGLES/FOURBALL: solo el scorer
        - FOURSOMES: el scorer + su companero de equipo (comparten score)
        """
        if match_format in (MatchFormat.SINGLES, MatchFormat.FOURBALL):
            return [scorer_user_id]

        return self._get_team_player_ids(team_a_players, team_b_players, scorer_user_id)

    def get_affected_marked_player_ids(
        self,
        team_a_players: tuple[MatchPlayer, ...],
        team_b_players: tuple[MatchPlayer, ...],
        marked_player_id: UserId,
        match_format: MatchFormat,
    ) -> list[UserId]:
        """
        Retorna los IDs de jugadores cuyos HoleScores reciben marker_score.

        - SINGLES/FOURBALL: solo el marked
        - FOURSOMES: los 2 jugadores del equipo marcado
        """
        if match_format in (MatchFormat.SINGLES, MatchFormat.FOURBALL):
            return [marked_player_id]

        # FOURSOMES: both players in marked team
        return self._get_team_player_ids(team_a_players, team_b_players, marked_player_id)

    def _get_team_player_ids(
        self,
        team_a_players: tuple[MatchPlayer, ...],
        team_b_players: tuple[MatchPlayer, ...],
        player_id: UserId,
    ) -> list[UserId]:
        """Retorna los IDs de todos los jugadores del equipo del player_id."""
        for p in team_a_players:
            if p.user_id == player_id:
                return [mp.user_id for mp in team_a_players]
        for p in team_b_players:
            if p.user_id == player_id:
                return [mp.user_id for mp in team_b_players]
        return [player_id]

    def calculate_ryder_cup_points(self, result: dict | None, status: str) -> dict:
        """
        Calcula los puntos Ryder Cup para un partido.

        Args:
            result: {winner: "A"/"B"/"HALVED", score: "..."} o None
            status: Estado del partido

        Returns:
            {team_a: float, team_b: float}
        """
        if result is None:
            return {"team_a": 0.0, "team_b": 0.0}

        winner = result.get("winner")

        if winner == "HALVED":
            return {"team_a": 0.5, "team_b": 0.5}
        if winner == "A":
            return {"team_a": 1.0, "team_b": 0.0}
        if winner == "B":
            return {"team_a": 0.0, "team_b": 1.0}

        return {"team_a": 0.0, "team_b": 0.0}
