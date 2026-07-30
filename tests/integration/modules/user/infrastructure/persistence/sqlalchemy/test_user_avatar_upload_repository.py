import pytest

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_avatar_upload import UserAvatarUpload
from src.modules.user.infrastructure.persistence.sqlalchemy.user_avatar_upload_repository import (
    SQLAlchemyUserAvatarUploadRepository,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)

pytestmark = pytest.mark.integration


async def _make_saved_user(db_session, email: str) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=email,
        plain_password="ValidPassword123!",
    )
    await SQLAlchemyUserRepository(db_session).save(user)
    await db_session.commit()
    return user


async def test_save_and_find_by_id(db_session):
    user = await _make_saved_user(db_session, "avatar-repo-1@example.com")
    repository = SQLAlchemyUserAvatarUploadRepository(db_session)
    upload = UserAvatarUpload.create(user_id=user.id, image_data=b"jpeg-bytes")

    await repository.save(upload)
    await db_session.commit()
    found = await repository.find_by_id(upload.id)

    assert found is not None
    assert found.id == upload.id
    assert found.user_id == user.id
    assert found.image_data == b"jpeg-bytes"
    assert found.content_type == "image/jpeg"


async def test_find_by_id_returns_none_when_missing(db_session):
    repository = SQLAlchemyUserAvatarUploadRepository(db_session)
    from src.modules.user.domain.value_objects.user_avatar_upload_id import UserAvatarUploadId

    found = await repository.find_by_id(UserAvatarUploadId.generate())

    assert found is None


async def test_find_by_user_orders_most_recent_first(db_session):
    user = await _make_saved_user(db_session, "avatar-repo-2@example.com")
    repository = SQLAlchemyUserAvatarUploadRepository(db_session)
    first = UserAvatarUpload.create(user_id=user.id, image_data=b"one")
    await repository.save(first)
    await db_session.commit()
    second = UserAvatarUpload.create(user_id=user.id, image_data=b"two")
    await repository.save(second)
    await db_session.commit()

    results = await repository.find_by_user(user.id)

    assert [u.id for u in results] == [second.id, first.id]


async def test_count_by_user_counts_without_loading_image_data(db_session):
    user = await _make_saved_user(db_session, "avatar-repo-3@example.com")
    repository = SQLAlchemyUserAvatarUploadRepository(db_session)
    assert await repository.count_by_user(user.id) == 0

    await repository.save(UserAvatarUpload.create(user_id=user.id, image_data=b"one"))
    await repository.save(UserAvatarUpload.create(user_id=user.id, image_data=b"two"))
    await db_session.commit()

    assert await repository.count_by_user(user.id) == 2


async def test_delete_removes_the_upload(db_session):
    user = await _make_saved_user(db_session, "avatar-repo-4@example.com")
    repository = SQLAlchemyUserAvatarUploadRepository(db_session)
    upload = UserAvatarUpload.create(user_id=user.id, image_data=b"jpeg-bytes")
    await repository.save(upload)
    await db_session.commit()

    await repository.delete(upload.id)
    await db_session.commit()

    assert await repository.find_by_id(upload.id) is None
