"""
ScoringService - Servicio de dominio para logica de scoring match play.

Contiene la logica de negocio pura para:
- Asignacion de marcadores
- Calculo de ganador por hoyo
- Standing del partido
- Determinacion de partido decidido
- Calculo de puntos Ryder Cup
"""

from src.modules.competition.domain.value_objects.marker_assignment import (
    MarkerAssignment,
)
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.user.domain.value_objects.user_id import UserId


class ScoringService:
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
            MarkerAssignment(scorer_user_id=a1.user_id, marks_user_id=b1.user_id, marked_by_user_id=b2.user_id),
            MarkerAssignment(scorer_user_id=a2.user_id, marks_user_id=b2.user_id, marked_by_user_id=b1.user_id),
            MarkerAssignment(scorer_user_id=b1.user_id, marks_user_id=a2.user_id, marked_by_user_id=a1.user_id),
            MarkerAssignment(scorer_user_id=b2.user_id, marks_user_id=a1.user_id, marked_by_user_id=a2.user_id),
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
            MarkerAssignment(scorer_user_id=a1.user_id, marks_user_id=b1.user_id, marked_by_user_id=b2.user_id),
            MarkerAssignment(scorer_user_id=a2.user_id, marks_user_id=b2.user_id, marked_by_user_id=b1.user_id),
            MarkerAssignment(scorer_user_id=b1.user_id, marks_user_id=a2.user_id, marked_by_user_id=a1.user_id),
            MarkerAssignment(scorer_user_id=b2.user_id, marks_user_id=a1.user_id, marked_by_user_id=a2.user_id),
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

    def calculate_hole_winner(
        self,
        team_a_net_scores: list[int | None],
        team_b_net_scores: list[int | None],
        match_format: MatchFormat,
    ) -> str:
        """
        Calcula el ganador de un hoyo.

        Args:
            team_a_net_scores: Net scores del equipo A (uno por jugador)
            team_b_net_scores: Net scores del equipo B (uno por jugador)
            match_format: Formato del partido

        Returns:
            "A", "B", o "HALVED"
        """
        best_a = self._best_ball(team_a_net_scores, match_format)
        best_b = self._best_ball(team_b_net_scores, match_format)

        if best_a is None and best_b is None:
            return "HALVED"
        if best_a is None:
            return "B"
        if best_b is None:
            return "A"

        if best_a < best_b:
            return "A"
        if best_b < best_a:
            return "B"
        return "HALVED"

    def _best_ball(
        self,
        net_scores: list[int | None],
        match_format: MatchFormat,
    ) -> int | None:
        """
        Retorna el mejor score (menor) del equipo.

        - SINGLES/FOURSOMES: unico score (o el primero no-None)
        - FOURBALL: mejor bola (menor net score)
        """
        valid = [s for s in net_scores if s is not None]
        if not valid:
            return None
        return min(valid)

    @staticmethod
    def find_best_ball_player(
        player_net_scores: list[tuple[str, int | None]],
    ) -> str | None:
        """
        Encuentra el jugador con la mejor bola (menor net score) en un equipo.

        Args:
            player_net_scores: Lista de (user_id, net_score) del equipo

        Returns:
            user_id del jugador con mejor net score, o None si no hay scores
        """
        best_uid = None
        best_score = None
        for uid, net in player_net_scores:
            if net is not None and (best_score is None or net < best_score):
                best_score = net
                best_uid = uid
        return best_uid

    def calculate_match_standing(
        self,
        hole_results: list[str],
    ) -> dict:
        """
        Calcula el standing actual del partido.

        Args:
            hole_results: Lista de resultados por hoyo ("A", "B", "HALVED")

        Returns:
            {status: "2UP"/"AS", leading_team: "A"/"B"/None,
             holes_played: int, holes_remaining: int}
        """
        a_wins = hole_results.count("A")
        b_wins = hole_results.count("B")
        holes_played = len(hole_results)
        holes_remaining = 18 - holes_played

        diff = a_wins - b_wins

        if diff == 0:
            return {
                "status": "AS",
                "leading_team": None,
                "holes_played": holes_played,
                "holes_remaining": holes_remaining,
            }

        leading_team = "A" if diff > 0 else "B"
        lead = abs(diff)

        return {
            "status": f"{lead}UP",
            "leading_team": leading_team,
            "holes_played": holes_played,
            "holes_remaining": holes_remaining,
        }

    def is_match_decided(self, standing: dict) -> bool:
        """
        Determina si el partido esta matematicamente decidido.

        Un partido esta decidido cuando la ventaja > hoyos restantes.
        """
        if standing["leading_team"] is None:
            return False

        lead = int(standing["status"].replace("UP", ""))
        return lead > standing["holes_remaining"]

    def format_decided_result(self, hole_results: list[str]) -> dict:
        """
        Formatea el resultado de un partido decidido.

        Returns:
            {winner: "A"/"B", score: "3&2"/"1UP"/"AS"}
        """
        standing = self.calculate_match_standing(hole_results)
        holes_remaining = standing["holes_remaining"]

        if standing["leading_team"] is None:
            return {"winner": "HALVED", "score": "AS"}

        lead = int(standing["status"].replace("UP", ""))

        if holes_remaining == 0:
            if lead == 0:
                return {"winner": "HALVED", "score": "AS"}
            return {"winner": standing["leading_team"], "score": f"{lead}UP"}

        # Early termination: N&M format
        return {
            "winner": standing["leading_team"],
            "score": f"{lead}&{holes_remaining}",
        }

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
