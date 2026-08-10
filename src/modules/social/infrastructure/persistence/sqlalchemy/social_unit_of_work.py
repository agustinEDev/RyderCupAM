"""Social Unit of Work - SQLAlchemy Implementation."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.social.domain.exceptions.social_violations import (
    DuplicateFriendshipViolation,
)
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivityEventRepositoryInterface,
)
from src.modules.social.domain.repositories.friendship_repository_interface import (
    FriendshipRepositoryInterface,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.infrastructure.persistence.sqlalchemy.activity_event_repository import (
    SQLAlchemyActivityEventRepository,
)
from src.modules.social.infrastructure.persistence.sqlalchemy.friendship_repository import (
    SQLAlchemyFriendshipRepository,
)

UQ_FRIENDSHIP_PAIR_CONSTRAINT = "uq_friendship_pair"


class SQLAlchemySocialUnitOfWork(SocialUnitOfWorkInterface):
    """Implementacion asincrona de la Unit of Work del modulo Social con SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._friendships = SQLAlchemyFriendshipRepository(session)
        self._activity_events = SQLAlchemyActivityEventRepository(session)

    @property
    def friendships(self) -> FriendshipRepositoryInterface:
        return self._friendships

    @property
    def activity_events(self) -> ActivityEventRepositoryInterface:
        return self._activity_events

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            await self.commit()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def flush(self) -> None:
        try:
            await self._session.flush()
        except IntegrityError as e:
            await self._session.rollback()
            if UQ_FRIENDSHIP_PAIR_CONSTRAINT in str(e.orig):
                raise DuplicateFriendshipViolation(
                    "A friendship or block relationship between these users "
                    "was just created concurrently."
                ) from e
            raise

    def is_active(self) -> bool:
        return self._session.is_active
