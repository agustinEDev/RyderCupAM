"""
SnakeDraftService Domain Service.

Implementa el sistema de draft en serpiente para asignación de equipos.

El Snake Draft garantiza equipos equilibrados alternando el orden de
selección entre capitanes. En la segunda ronda, el orden se invierte.

Ejemplo con 12 jugadores (ordenados por handicap):
- Ronda 1: Capitán A elige 1º, Capitán B elige 2º, ...
- Ronda 2: Capitán B elige 7º, Capitán A elige 8º, ... (orden invertido)

Resultado: Equipos equilibrados en términos de skill.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import TypeVar

from src.modules.user.domain.value_objects.user_id import UserId


class Team(str, Enum):
    """Equipo en la competición (A o B)."""

    A = "A"
    B = "B"

    def opposite(self) -> "Team":
        """Retorna el equipo contrario."""
        return Team.B if self == Team.A else Team.A


@dataclass
class PlayerForDraft:
    """
    Representa un jugador para el proceso de draft.

    Attributes:
        user_id: ID del usuario
        handicap: Handicap del jugador (menor = mejor)
        name: Nombre para display (opcional, para debugging)
    """

    user_id: UserId
    handicap: Decimal
    name: str = ""


@dataclass
class DraftResult:
    """
    Resultado del draft para un jugador.

    Attributes:
        user_id: ID del usuario
        team: Equipo asignado (A o B)
        draft_order: Orden en que fue seleccionado (1-indexed)
    """

    user_id: UserId
    team: Team
    draft_order: int


T = TypeVar("T")

MIN_DRAFT_PLAYERS = 2


class SnakeDraftService:
    """
    Servicio de dominio para asignación de equipos en formato Snake Draft.

    El Snake Draft es un algoritmo de asignación que:
    1. Ordena jugadores por handicap (mejor primero)
    2. Alterna asignaciones entre equipos en patrón serpiente
    3. Garantiza equipos equilibrados

    Patrón Snake (ejemplo 12 jugadores):
    Picks 1,2,3,4,5,6 → A,B,A,B,A,B
    Picks 7,8,9,10,11,12 → B,A,B,A,B,A (orden invertido)

    Uso:
        service = SnakeDraftService()
        results = service.assign_teams(players)
        for result in results:
            print(f"{result.user_id} → Team {result.team}, Pick #{result.draft_order}")
    """

    def assign_teams(
        self,
        players: list[PlayerForDraft],
        first_pick: Team = Team.A,
    ) -> list[DraftResult]:
        """
        Asigna equipos a los jugadores usando Snake Draft.

        Args:
            players: Lista de jugadores (se ordenarán por handicap)
            first_pick: Equipo que elige primero (default: A)

        Returns:
            Lista de DraftResult con las asignaciones

        Raises:
            ValueError: Si hay menos de 2 jugadores o número impar
        """
        if len(players) < MIN_DRAFT_PLAYERS:
            raise ValueError("Snake draft requires at least 2 players")

        if len(players) % 2 != 0:
            raise ValueError(
                f"Snake draft requires even number of players, got {len(players)}"
            )

        # Ordenar por handicap (menor primero = mejor jugador)
        sorted_players = sorted(players, key=lambda p: p.handicap)

        # Determinar tamaño de cada "ronda" del snake
        # Una ronda completa = 2 picks (uno por equipo)
        results: list[DraftResult] = []
        current_team = first_pick

        for i, player in enumerate(sorted_players):
            pick_number = i + 1

            results.append(
                DraftResult(
                    user_id=player.user_id,
                    team=current_team,
                    draft_order=pick_number,
                )
            )

            # Snake pattern: después de cada pick, alternar equipo
            # Pero en el "giro" del snake (cada 2 picks), mantener el mismo equipo
            # Patrón: A,B,B,A,A,B,B,A,A,B,B,A...
            # Esto se logra alternando EXCEPTO en los "bordes" (posiciones 2,4,6,...)
            if self._should_switch_team(pick_number):
                current_team = current_team.opposite()

        return results

    def _should_switch_team(self, pick_number: int) -> bool:
        """
        Determina si debe cambiar de equipo después de este pick.

        Patrón snake: A,B,B,A,A,B,B,A,A,B,B,A...
        - Pick 1: A → switch to B
        - Pick 2: B → NO switch (giro)
        - Pick 3: B → switch to A
        - Pick 4: A → NO switch (giro)
        - ...

        Regla: No cambiar si (pick_number % 2 == 0)
        """
        return pick_number % 2 != 0

    def validate_team_balance(
        self,
        results: list[DraftResult],
    ) -> bool:
        """
        Valida que los equipos estén balanceados.

        Args:
            results: Resultados del draft

        Returns:
            True si los equipos tienen el mismo número de jugadores
        """
        team_a_count = sum(1 for r in results if r.team == Team.A)
        team_b_count = sum(1 for r in results if r.team == Team.B)
        return team_a_count == team_b_count

    def get_team_players(
        self,
        results: list[DraftResult],
        team: Team,
    ) -> list[UserId]:
        """
        Obtiene los user_ids de un equipo específico.

        Args:
            results: Resultados del draft
            team: Equipo a filtrar

        Returns:
            Lista de UserIds del equipo (ordenados por draft_order)
        """
        return [
            r.user_id
            for r in sorted(results, key=lambda x: x.draft_order)
            if r.team == team
        ]
