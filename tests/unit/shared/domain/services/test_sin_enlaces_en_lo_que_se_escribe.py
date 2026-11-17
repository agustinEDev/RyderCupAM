"""
Donde no se deja escribir un enlace (SB-05, decidido por Agustín el 17 nov 2026):
el nombre de una competición, el alias y el mensaje de una invitación.
"""

from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import (
    CompetitionName,
    InvalidCompetitionNameError,
)
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.application.validation.validators import AliasValidator


def test_a_competition_name_with_a_link_is_rejected():
    with pytest.raises(InvalidCompetitionNameError, match="enlaces"):
        CompetitionName("Copa: gana en premio.com")


def test_an_ordinary_competition_name_still_works():
    assert CompetitionName("Copa St. Andrews 2026").value == "Copa St. Andrews 2026"


def test_an_alias_with_a_link_is_rejected():
    with pytest.raises(ValueError, match="enlaces"):
        AliasValidator.validate("premio.com")


def test_an_ordinary_alias_still_works():
    assert AliasValidator.validate("J.R. Trinx") == "J.R. Trinx"


def test_an_invitation_message_with_a_link_is_rejected():
    with pytest.raises(ValueError, match="enlaces"):
        Invitation.create(
            id=InvitationId.generate(),
            competition_id=CompetitionId(uuid4()),
            inviter_id=UserId(uuid4()),
            invitee_email="a@b.com",
            personal_message="Entra ya en www.premio.com/regalo",
        )


def test_an_invitation_without_links_is_created():
    invitacion = Invitation.create(
        id=InvitationId.generate(),
        competition_id=CompetitionId(uuid4()),
        inviter_id=UserId(uuid4()),
        invitee_email="a@b.com",
        personal_message="¡Te esperamos el sábado!",
    )
    assert invitacion.personal_message == "¡Te esperamos el sábado!"
