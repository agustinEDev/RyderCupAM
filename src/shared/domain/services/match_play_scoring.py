"""
MatchPlayScoring - Las reglas del match play (RyderCupAM#165).

Ganador de cada hoyo, mejor bola, cómo va el partido, si está decidido y el
resultado tipo 4&2. Lógica pura, sin IO.

Estaban en el `ScoringService` de competición y las usan también la partida
rápida y las estadísticas: viven en `shared`. `ScoringService` hereda de esta
clase y añade lo de la Ryder (marcadores y puntos).
"""

from collections.abc import Mapping

from src.shared.domain.value_objects.match_format import MatchFormat

TOTAL_HOLES = 18


class MatchPlayScoring:
    """Reglas del match play: puras, sin dependencias de framework ni IO."""

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
    ) -> list[str]:
        """
        Encuentra el/los jugador/es con la mejor bola (menor net score) en un equipo.

        Args:
            player_net_scores: Lista de (user_id, net_score) del equipo

        Returns:
            Lista de user_ids con el mejor net score. Vacía si no hay scores.
            Múltiples elementos en caso de empate.
        """
        best_score = None
        for _, net in player_net_scores:
            if net is not None and (best_score is None or net < best_score):
                best_score = net
        if best_score is None:
            return []
        return [uid for uid, net in player_net_scores if net == best_score]

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

    def decided_in_hole_order(self, results_by_hole: Mapping[int, str]) -> dict | None:
        """
        El resultado del partido si ya esta decidido, o None si sigue en juego
        (`holes_until_decided`).

        Args:
            results_by_hole: {numero de hoyo: "A"/"B"/"HALVED"} de los cerrados

        Returns:
            {winner, score} como `format_decided_result`, o None
        """
        hasta_la_decision = self.holes_until_decided(results_by_hole)
        if hasta_la_decision is None:
            return None
        return self.format_decided_result(hasta_la_decision)

    def holes_until_decided(self, results_by_hole: Mapping[int, str]) -> list[str] | None:
        """
        Los resultados del 1 al hoyo en que se decidio el partido, o None si
        sigue en juego.

        Se recorren los hoyos del 1 al 18 y se decide en el primero en que la
        ventaja supera a los que quedan, con todos los anteriores cerrados: un
        hoyo abierto antes espera a cerrarse, y lo anotado despues no cuenta
        (Agustin, 25 oct 2026). Contando los cerrados sin mirar su orden, un
        fourball con el 4 y el 5 abiertos se daba por decidido con un N&M que
        no habia ocurrido.
        """
        en_orden: list[str] = []
        for hoyo in range(1, TOTAL_HOLES + 1):
            if hoyo not in results_by_hole:
                return None
            en_orden.append(results_by_hole[hoyo])
            if self.is_match_decided(self.calculate_match_standing(en_orden)):
                return en_orden
        return None
