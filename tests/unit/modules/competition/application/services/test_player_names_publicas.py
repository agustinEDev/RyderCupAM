"""
PlayerNames y la regla del nombre real (SB-08, decidido el 17 nov 2026).

En una competición pública el nombre real va siempre a la vista, aunque el jugador
eligiera su alias; en una privada, lo que eligió.
"""

import pytest

from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.user.domain.entities.user import User


def _con_alias() -> User:
    user = User.create(
        first_name="Agustín",
        last_name="Estévez",
        email_str="agustin.alias@kind-pruebas-rcf.com",
        plain_password="Clave-De-Prueba-1!",
    )
    user.update_profile(alias="Trinx")
    return user


def _eligio(user: User, use_real_name: bool) -> Enrollment:
    inscripcion = Enrollment.request(EnrollmentId.generate(), CompetitionId.generate(), user.id)
    inscripcion.set_name_preference(use_real_name)
    return inscripcion


@pytest.mark.parametrize(
    "visibility, use_real_name, esperado",
    [
        (Visibility.PUBLIC, False, "Agustín Estévez"),
        (Visibility.PUBLIC, True, "Agustín Estévez"),
        (Visibility.PRIVATE, False, "Trinx"),
        (Visibility.PRIVATE, True, "Agustín Estévez"),
    ],
    ids=["publica-alias", "publica-nombre", "privada-alias", "privada-nombre"],
)
def test_the_name_follows_the_competition_rule(visibility, use_real_name, esperado):
    """
    Given: Un jugador con alias inscrito, que eligió su alias o su nombre
    When: Se pide su nombre en una competición pública o privada
    Then: En la pública, el real; en la privada, lo que eligió
    """
    user = _con_alias()

    nombres = PlayerNames.de_lo_leido(
        [user.id], {user.id: user}, [_eligio(user, use_real_name)], visibility
    )

    assert nombres[user.id] == esperado
