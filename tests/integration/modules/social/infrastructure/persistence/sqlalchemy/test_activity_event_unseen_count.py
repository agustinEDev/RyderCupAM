"""Tests de integracion del recuento de novedades del feed, con su tope."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.persistence.sqlalchemy.activity_event_repository import (
    SQLAlchemyActivityEventRepository,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)

pytestmark = pytest.mark.integration

VISITA = datetime(2026, 8, 10, 12, 0)
TIPOS = frozenset({ActivityEventType.BIRDIE})


async def _user(db_session) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"cnt-{uuid4().hex[:8]}@example.com",
        plain_password="ValidPassword123!",
    )
    await SQLAlchemyUserRepository(db_session).save(user)
    await db_session.commit()
    return user


def _eventos(user, cuantos, desde, jugado=VISITA - timedelta(days=3), visible=True):
    return [
        ActivityEvent.create(
            user_id=user.id,
            type=ActivityEventType.BIRDIE,
            occurred_at=jugado,
            source_match_id=f"m-{uuid4().hex[:8]}",
            published_at=desde + timedelta(minutes=i),
            visible_to_friends=visible,
        )
        for i in range(cuantos)
    ]


async def test_cuenta_por_publicacion_y_no_por_juego(db_session):
    """
    Given logros jugados antes de la visita, unos publicados antes y otros
    despues / When se cuentan / Then solo los publicados despues.
    """
    user = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        _eventos(user, 2, VISITA - timedelta(hours=2))
        + _eventos(user, 3, VISITA + timedelta(minutes=1))
    )
    await db_session.commit()

    cuenta = await repository.count_in(
        [ActivitySlice(user_ids=(user.id,), types=TIPOS)], since=VISITA, cap=10
    )

    assert cuenta == 3


async def test_c12_el_tope_corta_en_diez(db_session):
    """C12. Given 12 novedades / When se cuentan con tope 10 / Then 10."""
    user = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(_eventos(user, 12, VISITA + timedelta(minutes=1)))
    await db_session.commit()

    cuenta = await repository.count_in(
        [ActivitySlice(user_ids=(user.id,), types=TIPOS)], since=VISITA, cap=10
    )

    assert cuenta == 10


async def test_c11_sin_visita_cuenta_todo(db_session):
    """C11. Given logros de cualquier fecha / When se cuenta sin visita previa / Then todos."""
    user = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(_eventos(user, 4, VISITA - timedelta(days=30)))
    await db_session.commit()

    cuenta = await repository.count_in(
        [ActivitySlice(user_ids=(user.id,), types=TIPOS)], since=None, cap=10
    )

    assert cuenta == 4


async def test_el_recuento_respeta_la_visibilidad_de_cada_trozo(db_session):
    """
    Given un autor con un logro oculto y otro visible / When se cuenta como
    amigo y como autor / Then 1 y 2.
    """
    autor = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        _eventos(autor, 1, VISITA + timedelta(minutes=1))
        + _eventos(autor, 1, VISITA + timedelta(minutes=5), visible=False)
    )
    await db_session.commit()

    como_amigo = await repository.count_in(
        [ActivitySlice(user_ids=(autor.id,), types=TIPOS, only_visible_to_friends=True)],
        since=VISITA,
        cap=10,
    )
    como_autor = await repository.count_in(
        [ActivitySlice(user_ids=(autor.id,), types=TIPOS)], since=VISITA, cap=10
    )

    assert (como_amigo, como_autor) == (1, 2)


async def test_sin_trozos_no_cuenta_nada(db_session):
    """Given ningun trozo / When se cuenta / Then 0 sin consultar."""
    repository = SQLAlchemyActivityEventRepository(db_session)

    assert await repository.count_in([], since=VISITA, cap=10) == 0
