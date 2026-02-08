"""Tests para SnakeDraftService domain service."""

from decimal import Decimal

import pytest

from src.modules.competition.domain.services.snake_draft_service import (
    DraftResult,
    PlayerForDraft,
    SnakeDraftService,
    Team,
)
from src.modules.user.domain.value_objects.user_id import UserId


class TestTeam:
    """Tests para Team enum"""

    def test_team_a_opposite_is_b(self):
        """Team A → Team B."""
        assert Team.A.opposite() == Team.B

    def test_team_b_opposite_is_a(self):
        """Team B → Team A."""
        assert Team.B.opposite() == Team.A


class TestPlayerForDraft:
    """Tests para PlayerForDraft dataclass"""

    def test_create_player_for_draft(self):
        """Crea PlayerForDraft correctamente."""
        user_id = UserId.generate()
        player = PlayerForDraft(
            user_id=user_id,
            handicap=Decimal("12.4"),
            name="John Doe",
        )

        assert player.user_id == user_id
        assert player.handicap == Decimal("12.4")
        assert player.name == "John Doe"

    def test_name_is_optional(self):
        """Name es opcional, default ''."""
        player = PlayerForDraft(
            user_id=UserId.generate(),
            handicap=Decimal("10.0"),
        )

        assert player.name == ""


class TestSnakeDraftServiceBasic:
    """Tests básicos para SnakeDraftService"""

    def test_assign_two_players(self):
        """Asigna 2 jugadores correctamente."""
        service = SnakeDraftService()
        players = [
            PlayerForDraft(UserId.generate(), Decimal("10.0"), "Player A"),
            PlayerForDraft(UserId.generate(), Decimal("15.0"), "Player B"),
        ]

        results = service.assign_teams(players)

        assert len(results) == 2
        # Mejor jugador (HI=10) va primero
        assert results[0].team == Team.A
        assert results[0].draft_order == 1
        assert results[1].team == Team.B
        assert results[1].draft_order == 2

    def test_assign_four_players_snake_pattern(self):
        """4 jugadores siguen patrón serpiente: A, B, B, A."""
        service = SnakeDraftService()
        players = [
            PlayerForDraft(UserId.generate(), Decimal("5.0")),  # Best
            PlayerForDraft(UserId.generate(), Decimal("10.0")),
            PlayerForDraft(UserId.generate(), Decimal("15.0")),
            PlayerForDraft(UserId.generate(), Decimal("20.0")),  # Worst
        ]

        results = service.assign_teams(players)

        teams = [r.team for r in results]
        # Patrón: A, B, B, A
        assert teams == [Team.A, Team.B, Team.B, Team.A]

    def test_assign_six_players_snake_pattern(self):
        """6 jugadores siguen patrón serpiente: A, B, B, A, A, B."""
        service = SnakeDraftService()
        players = [PlayerForDraft(UserId.generate(), Decimal(str(i * 2))) for i in range(1, 7)]

        results = service.assign_teams(players)

        teams = [r.team for r in results]
        # Patrón: A, B, B, A, A, B
        assert teams == [Team.A, Team.B, Team.B, Team.A, Team.A, Team.B]

    def test_assign_twelve_players_snake_pattern(self):
        """12 jugadores (formato Ryder Cup) siguen patrón correcto."""
        service = SnakeDraftService()
        players = [PlayerForDraft(UserId.generate(), Decimal(str(i))) for i in range(1, 13)]

        results = service.assign_teams(players)

        teams = [r.team for r in results]
        # Patrón para 12: A,B,B,A,A,B,B,A,A,B,B,A
        expected = [
            Team.A,
            Team.B,
            Team.B,
            Team.A,
            Team.A,
            Team.B,
            Team.B,
            Team.A,
            Team.A,
            Team.B,
            Team.B,
            Team.A,
        ]
        assert teams == expected

    def test_players_sorted_by_handicap(self):
        """Los jugadores se ordenan por handicap antes del draft."""
        service = SnakeDraftService()

        worst = PlayerForDraft(UserId.generate(), Decimal("25.0"), "Worst")
        best = PlayerForDraft(UserId.generate(), Decimal("5.0"), "Best")
        middle = PlayerForDraft(UserId.generate(), Decimal("15.0"), "Middle")
        good = PlayerForDraft(UserId.generate(), Decimal("8.0"), "Good")

        # Orden desordenado
        players = [worst, middle, best, good]

        results = service.assign_teams(players)

        # Verificar que best (HI=5) es pick 1
        best_result = next(r for r in results if r.user_id == best.user_id)
        assert best_result.draft_order == 1

        # Verificar que worst (HI=25) es pick 4
        worst_result = next(r for r in results if r.user_id == worst.user_id)
        assert worst_result.draft_order == 4


class TestSnakeDraftServiceFirstPick:
    """Tests para configuración de primer pick"""

    def test_team_b_first_pick(self):
        """Team B puede elegir primero."""
        service = SnakeDraftService()
        players = [
            PlayerForDraft(UserId.generate(), Decimal("10.0")),
            PlayerForDraft(UserId.generate(), Decimal("15.0")),
        ]

        results = service.assign_teams(players, first_pick=Team.B)

        assert results[0].team == Team.B
        assert results[1].team == Team.A


class TestSnakeDraftServiceValidation:
    """Tests para validación de entrada"""

    def test_less_than_two_players_raises(self):
        """Error si hay menos de 2 jugadores."""
        service = SnakeDraftService()
        players = [PlayerForDraft(UserId.generate(), Decimal("10.0"))]

        with pytest.raises(ValueError, match="at least 2 players"):
            service.assign_teams(players)

    def test_empty_players_raises(self):
        """Error si lista vacía."""
        service = SnakeDraftService()

        with pytest.raises(ValueError, match="at least 2 players"):
            service.assign_teams([])

    def test_odd_number_of_players_raises(self):
        """Error si número impar de jugadores."""
        service = SnakeDraftService()
        players = [
            PlayerForDraft(UserId.generate(), Decimal(str(i)))
            for i in range(1, 6)  # 5 jugadores
        ]

        with pytest.raises(ValueError, match="even number of players"):
            service.assign_teams(players)


class TestSnakeDraftServiceHelpers:
    """Tests para métodos auxiliares"""

    def test_validate_team_balance_true(self):
        """validate_team_balance retorna True si balanceados."""
        service = SnakeDraftService()
        results = [
            DraftResult(UserId.generate(), Team.A, 1),
            DraftResult(UserId.generate(), Team.B, 2),
            DraftResult(UserId.generate(), Team.B, 3),
            DraftResult(UserId.generate(), Team.A, 4),
        ]

        assert service.validate_team_balance(results) is True

    def test_validate_team_balance_false(self):
        """validate_team_balance retorna False si no balanceados."""
        service = SnakeDraftService()
        results = [
            DraftResult(UserId.generate(), Team.A, 1),
            DraftResult(UserId.generate(), Team.A, 2),
            DraftResult(UserId.generate(), Team.B, 3),
        ]

        assert service.validate_team_balance(results) is False

    def test_get_team_players(self):
        """get_team_players retorna los user_ids del equipo."""
        service = SnakeDraftService()

        user1 = UserId.generate()
        user2 = UserId.generate()
        user3 = UserId.generate()
        user4 = UserId.generate()

        results = [
            DraftResult(user1, Team.A, 1),
            DraftResult(user2, Team.B, 2),
            DraftResult(user3, Team.B, 3),
            DraftResult(user4, Team.A, 4),
        ]

        team_a = service.get_team_players(results, Team.A)
        team_b = service.get_team_players(results, Team.B)

        assert team_a == [user1, user4]  # Ordenados por draft_order
        assert team_b == [user2, user3]


class TestSnakeDraftServiceIntegration:
    """Tests de integración para SnakeDraftService"""

    def test_full_ryder_cup_scenario(self):
        """Escenario completo estilo Ryder Cup (12 jugadores)."""
        service = SnakeDraftService()

        # Crear 12 jugadores con handicaps variados
        players = [
            PlayerForDraft(UserId.generate(), Decimal("2.0"), "Pro 1"),
            PlayerForDraft(UserId.generate(), Decimal("4.5"), "Pro 2"),
            PlayerForDraft(UserId.generate(), Decimal("6.2"), "Scratch 1"),
            PlayerForDraft(UserId.generate(), Decimal("8.0"), "Scratch 2"),
            PlayerForDraft(UserId.generate(), Decimal("10.3"), "Low 1"),
            PlayerForDraft(UserId.generate(), Decimal("12.1"), "Low 2"),
            PlayerForDraft(UserId.generate(), Decimal("14.5"), "Mid 1"),
            PlayerForDraft(UserId.generate(), Decimal("16.8"), "Mid 2"),
            PlayerForDraft(UserId.generate(), Decimal("18.2"), "High 1"),
            PlayerForDraft(UserId.generate(), Decimal("20.0"), "High 2"),
            PlayerForDraft(UserId.generate(), Decimal("22.5"), "High 3"),
            PlayerForDraft(UserId.generate(), Decimal("25.0"), "High 4"),
        ]

        results = service.assign_teams(players)

        # Verificar balance
        assert service.validate_team_balance(results)

        # Verificar 6 jugadores por equipo
        team_a = service.get_team_players(results, Team.A)
        team_b = service.get_team_players(results, Team.B)

        assert len(team_a) == 6
        assert len(team_b) == 6

    def test_snake_produces_fair_teams(self):
        """El snake draft produce equipos equilibrados."""
        service = SnakeDraftService()

        # Crear jugadores con handicaps 1-12
        players = [
            PlayerForDraft(UserId.generate(), Decimal(str(i)), f"P{i}") for i in range(1, 13)
        ]

        results = service.assign_teams(players)

        # Calcular suma de handicaps por equipo
        team_a_hcps = []
        team_b_hcps = []

        for i, result in enumerate(results):
            hcp = i + 1  # Handicap corresponde al orden (1-12)
            if result.team == Team.A:
                team_a_hcps.append(hcp)
            else:
                team_b_hcps.append(hcp)

        sum_a = sum(team_a_hcps)
        sum_b = sum(team_b_hcps)

        # Patrón A,B,B,A,A,B,B,A,A,B,B,A
        # Team A: picks 1,4,5,8,9,12 → handicaps 1,4,5,8,9,12 = 39
        # Team B: picks 2,3,6,7,10,11 → handicaps 2,3,6,7,10,11 = 39
        assert sum_a == sum_b == 39

    def test_consistent_results(self):
        """Mismos jugadores producen mismos resultados."""
        service = SnakeDraftService()

        # Crear jugadores con IDs fijos
        fixed_ids = [UserId.generate() for _ in range(4)]
        players = [
            PlayerForDraft(fixed_ids[0], Decimal("5.0")),
            PlayerForDraft(fixed_ids[1], Decimal("10.0")),
            PlayerForDraft(fixed_ids[2], Decimal("15.0")),
            PlayerForDraft(fixed_ids[3], Decimal("20.0")),
        ]

        results1 = service.assign_teams(players)
        results2 = service.assign_teams(players)

        # Mismas asignaciones
        for r1, r2 in zip(results1, results2, strict=True):
            assert r1.user_id == r2.user_id
            assert r1.team == r2.team
            assert r1.draft_order == r2.draft_order
