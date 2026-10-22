"""Un `payload` con ids ilegibles no tumba el feed: lo que no se lee se ignora."""

from uuid import uuid4

from src.modules.social.application.use_cases.get_friends_feed_use_case import _nombrados
from src.modules.user.domain.value_objects.user_id import UserId


def test_un_id_que_no_es_uuid_se_ignora():
    """Given rivales con un id basura / When se leen / Then sale solo el legible."""
    bueno = str(uuid4())
    payload = {
        "opponent_ids": ["no-es-un-uuid", bueno],
        "opponents": [{"user_id": "tampoco"}, {"name": "Invitado"}],
    }

    assert _nombrados(payload) == {UserId(bueno)}
