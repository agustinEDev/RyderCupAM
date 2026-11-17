"""
Donde no se deja escribir un enlace (SB-05, decidido por Agustín el 17 nov 2026):
el nombre de una competición, el alias y el mensaje de una invitación.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.modules.competition.domain.entities.invitation import (
    Invitation,
    InvitationMessageWithLinkError,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import (
    CompetitionName,
    InvalidCompetitionNameError,
)
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.infrastructure.api.v1.invitation_routes import (
    SendInvitationByEmailBody,
    SendInvitationByUserIdBody,
)
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
    with pytest.raises(InvitationMessageWithLinkError) as error:
        Invitation.create(
            id=InvitationId.generate(),
            competition_id=CompetitionId(uuid4()),
            inviter_id=UserId(uuid4()),
            invitee_email="a@b.com",
            personal_message="Entra ya en www.premio.com/regalo",
        )
    assert error.value.error_code == "MESSAGE_HAS_LINK"


@pytest.mark.parametrize("body", [SendInvitationByUserIdBody, SendInvitationByEmailBody])
def test_the_request_is_rejected_before_spending_the_invitation_quota(body):
    """
    Given: Una petición de invitación con un enlace en el mensaje
    When: La API la lee
    Then: Se rechaza ahí (422), antes del caso de uso y de su cupo por hora
    """
    destino = (
        {"invitee_user_id": str(uuid4())}
        if body is SendInvitationByUserIdBody
        else {"invitee_email": "a@b.com"}
    )
    with pytest.raises(ValidationError):
        body(**destino, personal_message="gana en premio.com")


def test_an_invitation_without_links_is_created():
    invitacion = Invitation.create(
        id=InvitationId.generate(),
        competition_id=CompetitionId(uuid4()),
        inviter_id=UserId(uuid4()),
        invitee_email="a@b.com",
        personal_message="¡Te esperamos el sábado!",
    )
    assert invitacion.personal_message == "¡Te esperamos el sábado!"
