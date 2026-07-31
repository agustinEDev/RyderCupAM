"""
Tests para los métodos de avatar de la entidad User y para UserAvatarUpload.

Arquitectura:
- Capa: Unit Tests (Domain)
- Módulo: User
- Feature: Avatar (v2.3.0)
"""

import pytest

from src.modules.user.domain.entities.user import AVATAR_PRESET_COUNT, User
from src.modules.user.domain.entities.user_avatar_upload import UserAvatarUpload
from src.modules.user.domain.errors.user_errors import InvalidAvatarPresetError
from src.modules.user.domain.value_objects.avatar_source import AvatarSource
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_avatar_upload_id import UserAvatarUploadId
from src.modules.user.domain.value_objects.user_id import UserId


def make_user() -> User:
    return User(
        id=UserId.generate(),
        email=Email("player@example.com"),
        password=Password.from_plain_text("s3cur3P@ssw0rd!"),
        first_name="Ana",
        last_name="García",
    )


class TestUserAvatarDefaults:
    def test_new_user_has_no_avatar_by_default(self):
        user = make_user()

        assert user.avatar_source == AvatarSource.NONE
        assert user.avatar_preset_id is None
        assert user.active_avatar_upload_id is None


class TestSetPresetAvatar:
    def test_set_preset_avatar_activates_preset(self):
        user = make_user()

        user.set_preset_avatar(3)

        assert user.avatar_source == AvatarSource.PRESET
        assert user.avatar_preset_id == 3
        assert user.active_avatar_upload_id is None

    def test_set_preset_avatar_rejects_preset_id_below_range(self):
        user = make_user()

        with pytest.raises(InvalidAvatarPresetError):
            user.set_preset_avatar(0)

    def test_set_preset_avatar_rejects_preset_id_above_range(self):
        user = make_user()

        with pytest.raises(InvalidAvatarPresetError):
            user.set_preset_avatar(AVATAR_PRESET_COUNT + 1)

    def test_set_preset_avatar_clears_previously_active_upload(self):
        user = make_user()
        upload_id = UserAvatarUploadId.generate()
        user.set_uploaded_avatar(upload_id)

        user.set_preset_avatar(1)

        assert user.avatar_source == AvatarSource.PRESET
        assert user.active_avatar_upload_id is None


class TestSetUploadedAvatar:
    def test_set_uploaded_avatar_activates_upload_and_clears_preset(self):
        user = make_user()
        user.set_preset_avatar(5)
        upload_id = UserAvatarUploadId.generate()

        user.set_uploaded_avatar(upload_id)

        assert user.avatar_source == AvatarSource.UPLOAD
        assert user.active_avatar_upload_id == upload_id
        assert user.avatar_preset_id is None


class TestClearAvatar:
    def test_clear_avatar_resets_to_none(self):
        user = make_user()
        user.set_preset_avatar(2)

        user.clear_avatar()

        assert user.avatar_source == AvatarSource.NONE
        assert user.avatar_preset_id is None
        assert user.active_avatar_upload_id is None


class TestUserAvatarUploadEntity:
    def test_create_generates_id_and_defaults_content_type(self):
        user_id = UserId.generate()

        upload = UserAvatarUpload.create(user_id=user_id, image_data=b"fake-jpeg-bytes")

        assert upload.id is not None
        assert upload.user_id == user_id
        assert upload.image_data == b"fake-jpeg-bytes"
        assert upload.content_type == "image/jpeg"
        assert upload.created_at is not None

    def test_rejects_empty_image_data(self):
        with pytest.raises(ValueError):
            UserAvatarUpload(
                id=None,
                user_id=UserId.generate(),
                image_data=b"",
                content_type="image/jpeg",
            )
