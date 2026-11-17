"""
Cuándo va a la vista el nombre real de un jugador (SB-08, decidido el 17 nov 2026).

Pública: siempre, con el alias además si lo tiene. Privada: lo que eligió al apuntarse.
"""

import pytest

from src.modules.competition.domain.value_objects.visibility import Visibility


@pytest.mark.parametrize("chosen", [True, False], ids=["eligio-nombre", "eligio-alias"])
def test_a_public_competition_always_shows_the_real_name(chosen):
    """
    Given: Una competición pública
    When: Un jugador eligió su nombre o su alias
    Then: Su nombre real va a la vista
    """
    assert Visibility.PUBLIC.shows_real_name(chosen) is True


@pytest.mark.parametrize("chosen", [True, False], ids=["eligio-nombre", "eligio-alias"])
def test_a_private_competition_follows_the_player_choice(chosen):
    """
    Given: Una competición privada
    When: Un jugador eligió su nombre o su alias
    Then: Se hace lo que eligió
    """
    assert Visibility.PRIVATE.shows_real_name(chosen) is chosen
