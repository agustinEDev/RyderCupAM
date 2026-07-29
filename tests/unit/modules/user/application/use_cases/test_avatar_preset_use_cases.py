"""
Tests para ListAvatarPresetsUseCase y GetAvatarPresetImageUseCase, incluyendo el
adaptador real FileSystemAvatarPresetProvider contra los assets empaquetados
(las 10 fotos de golf en src/modules/user/infrastructure/static/avatar_presets/).
"""

import pytest

from src.modules.user.application.use_cases.get_avatar_preset_image_use_case import (
    GetAvatarPresetImageUseCase,
)
from src.modules.user.application.use_cases.list_avatar_presets_use_case import (
    ListAvatarPresetsUseCase,
)
from src.modules.user.domain.entities.user import AVATAR_PRESET_COUNT
from src.modules.user.domain.errors.user_errors import InvalidAvatarPresetError
from src.modules.user.infrastructure.external.filesystem_avatar_preset_provider import (
    FileSystemAvatarPresetProvider,
)


@pytest.mark.asyncio
class TestListAvatarPresetsUseCase:
    async def test_lists_all_presets_with_image_url(self):
        use_case = ListAvatarPresetsUseCase()

        presets = await use_case.execute()

        assert len(presets) == AVATAR_PRESET_COUNT
        assert presets[0].id == 1
        assert presets[0].image_url == "/api/v1/avatar-presets/1/image"
        assert presets[-1].id == AVATAR_PRESET_COUNT


@pytest.mark.asyncio
class TestGetAvatarPresetImageUseCase:
    async def test_returns_real_jpeg_bytes_for_each_preset(self):
        use_case = GetAvatarPresetImageUseCase(FileSystemAvatarPresetProvider())

        for preset_id in range(1, AVATAR_PRESET_COUNT + 1):
            image_bytes, content_type = await use_case.execute(preset_id)
            assert content_type == "image/jpeg"
            assert image_bytes.startswith(b"\xff\xd8\xff")  # JPEG magic bytes
            assert len(image_bytes) > 1000

    async def test_raises_for_out_of_range_preset_id(self):
        use_case = GetAvatarPresetImageUseCase(FileSystemAvatarPresetProvider())

        with pytest.raises(InvalidAvatarPresetError):
            await use_case.execute(AVATAR_PRESET_COUNT + 1)

        with pytest.raises(InvalidAvatarPresetError):
            await use_case.execute(0)
