"""
Tests para UploadAvatarUseCase.

Usa un IImageProcessor falso (sin Pillow real) para mantener el test unitario
rápido y aislado; el procesado real con Pillow se cubre en tests de integración.
"""

import pytest

from src.modules.user.application.ports.image_processor_interface import IImageProcessor
from src.modules.user.application.use_cases.upload_avatar_use_case import (
    MAX_UPLOAD_BYTES,
    UploadAvatarUseCase,
)
from src.modules.user.domain.entities.user import AVATAR_MAX_STORED_UPLOADS, User
from src.modules.user.domain.errors.user_errors import (
    AvatarUploadTooLargeError,
    InvalidAvatarImageError,
    UserNotFoundError,
)
from src.modules.user.domain.value_objects.avatar_source import AvatarSource
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


class FakeImageProcessor(IImageProcessor):
    """Procesador falso: simula la salida de Pillow sin decodificar nada de verdad."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    def process_avatar_image(self, raw_bytes: bytes) -> bytes:
        if self.should_fail:
            raise InvalidAvatarImageError("El archivo subido no es una imagen válida")
        return b"processed-jpeg-bytes"


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


async def _make_saved_user(uow: InMemoryUnitOfWork) -> User:
    user = User(
        id=UserId.generate(),
        email=Email("player@example.com"),
        password=Password.from_plain_text("s3cur3P@ssw0rd!"),
        first_name="Ana",
        last_name="García",
    )
    await uow.users.save(user)
    return user


@pytest.mark.asyncio
class TestUploadAvatarUseCase:
    async def test_uploads_and_activates_new_avatar(self, uow):
        user = await _make_saved_user(uow)
        use_case = UploadAvatarUseCase(uow, FakeImageProcessor())

        response = await use_case.execute(str(user.id.value), b"raw-bytes")

        assert response.is_active is True
        stored_user = await uow.users.find_by_id(user.id)
        assert stored_user.avatar_source == AvatarSource.UPLOAD
        uploads = await uow.avatar_uploads.find_by_user(user.id)
        assert len(uploads) == 1
        assert uploads[0].image_data == b"processed-jpeg-bytes"

    async def test_raises_when_user_not_found(self, uow):
        use_case = UploadAvatarUseCase(uow, FakeImageProcessor())

        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(UserId.generate().value), b"raw-bytes")

    async def test_raises_when_file_too_large(self, uow):
        user = await _make_saved_user(uow)
        use_case = UploadAvatarUseCase(uow, FakeImageProcessor())
        oversized = b"x" * (MAX_UPLOAD_BYTES + 1)

        with pytest.raises(AvatarUploadTooLargeError):
            await use_case.execute(str(user.id.value), oversized)

    async def test_raises_when_image_processor_rejects_invalid_image(self, uow):
        user = await _make_saved_user(uow)
        use_case = UploadAvatarUseCase(uow, FakeImageProcessor(should_fail=True))

        with pytest.raises(InvalidAvatarImageError):
            await use_case.execute(str(user.id.value), b"not-an-image")

    async def test_prunes_oldest_upload_beyond_history_limit(self, uow):
        user = await _make_saved_user(uow)
        use_case = UploadAvatarUseCase(uow, FakeImageProcessor())

        uploaded_ids = []
        for _ in range(AVATAR_MAX_STORED_UPLOADS + 1):
            response = await use_case.execute(str(user.id.value), b"raw-bytes")
            uploaded_ids.append(response.id)

        remaining = await uow.avatar_uploads.find_by_user(user.id)
        assert len(remaining) == AVATAR_MAX_STORED_UPLOADS
        remaining_ids = {str(u.id.value) for u in remaining}
        # El primero subido debe haber sido podado (FIFO)
        assert str(uploaded_ids[0]) not in remaining_ids
        # El último subido (activo) debe seguir presente
        assert str(uploaded_ids[-1]) in remaining_ids
