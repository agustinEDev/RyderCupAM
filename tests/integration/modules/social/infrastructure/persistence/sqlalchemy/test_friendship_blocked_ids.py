"""Tests de integracion de `find_blocked_ids` (revision de BE-2, punto 3)."""

from uuid import uuid4

import pytest

from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.sqlalchemy.friendship_repository import (
    SQLAlchemyFriendshipRepository,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)

pytestmark = pytest.mark.integration


async def _user(db_session) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"blk-{uuid4().hex[:8]}@example.com",
        plain_password="ValidPassword123!",
    )
    await SQLAlchemyUserRepository(db_session).save(user)
    await db_session.commit()
    return user


async def _relacion(db_session, a: User, b: User, bloqueo: bool) -> None:
    amistad = Friendship.create(id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id)
    if bloqueo:
        amistad.block(a.id)
    else:
        amistad.accept()
    await SQLAlchemyFriendshipRepository(db_session).add(amistad)
    await db_session.commit()


async def test_devuelve_los_bloqueos_en_las_dos_direcciones(db_session):
    """Given bloqueos mios, contra mi, una amistad y uno ajeno / Then solo los dos mios."""
    yo, bloque, me_bloqueo, amigo, otro = [await _user(db_session) for _ in range(5)]
    await _relacion(db_session, yo, bloque, bloqueo=True)
    await _relacion(db_session, me_bloqueo, yo, bloqueo=True)
    await _relacion(db_session, yo, amigo, bloqueo=False)
    await _relacion(db_session, amigo, otro, bloqueo=True)

    bloqueados = await SQLAlchemyFriendshipRepository(db_session).find_blocked_ids(yo.id)

    assert set(bloqueados) == {bloque.id, me_bloqueo.id}
