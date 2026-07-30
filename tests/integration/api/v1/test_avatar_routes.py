"""
Tests E2E para Avatar Endpoints.

Tests de integración contra BD real (fixture `client`, BD efímera por test) que
verifican el flujo completo: presets fijos, subida real (Pillow de verdad),
historial acotado, cambio entre preset/subida y servido de la imagen activa.
"""

import io

import pytest
from httpx import AsyncClient
from PIL import Image

from tests.conftest import create_authenticated_user, set_auth_cookies


def _make_jpeg_bytes(width: int = 300, height: int = 200, color=(20, 120, 40)) -> bytes:
    image = Image.new("RGB", (width, height), color=color)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    return buffer.getvalue()


class TestAvatarPresetsPublicEndpoints:
    @pytest.mark.asyncio
    async def test_list_avatar_presets_returns_ten_items(self, client: AsyncClient):
        response = await client.get("/api/v1/avatar-presets")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10
        assert data[0]["id"] == 1
        assert data[0]["image_url"] == "/api/v1/avatar-presets/1/image"

    @pytest.mark.asyncio
    async def test_get_avatar_preset_image_returns_real_jpeg(self, client: AsyncClient):
        response = await client.get("/api/v1/avatar-presets/5/image")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.content.startswith(b"\xff\xd8\xff")

    @pytest.mark.asyncio
    async def test_get_avatar_preset_image_has_long_lived_cache_headers(
        self, client: AsyncClient
    ):
        response = await client.get("/api/v1/avatar-presets/5/image")

        assert response.status_code == 200
        assert "immutable" in response.headers["cache-control"]
        assert "max-age=31536000" in response.headers["cache-control"]
        assert response.headers["etag"]

    @pytest.mark.asyncio
    async def test_get_avatar_preset_image_out_of_range_returns_404(self, client: AsyncClient):
        response = await client.get("/api/v1/avatar-presets/99/image")

        assert response.status_code == 404


class TestSetAndGetActiveAvatar:
    @pytest.mark.asyncio
    async def test_set_preset_avatar_and_fetch_it(self, client: AsyncClient):
        user = await create_authenticated_user(
            client, "avatar_preset@test.com", "P@ssw0rd123!", "Avatar", "Preset"
        )
        set_auth_cookies(client, user["cookies"])

        set_response = await client.post(
            "/api/v1/users/me/avatar/preset", json={"preset_id": 3}
        )
        assert set_response.status_code == 200
        assert set_response.json()["avatar_source"] == "PRESET"
        assert set_response.json()["avatar_preset_id"] == 3

        user_id = user["user"]["id"]
        image_response = await client.get(f"/api/v1/users/{user_id}/avatar")
        preset_image_response = await client.get("/api/v1/avatar-presets/3/image")

        assert image_response.status_code == 200
        assert image_response.content == preset_image_response.content

    @pytest.mark.asyncio
    async def test_user_without_avatar_returns_404(self, client: AsyncClient):
        user = await create_authenticated_user(
            client, "avatar_none@test.com", "P@ssw0rd123!", "Avatar", "None"
        )
        set_auth_cookies(client, user["cookies"])
        user_id = user["user"]["id"]

        response = await client.get(f"/api/v1/users/{user_id}/avatar")

        assert response.status_code == 404


class TestUploadAvatar:
    @pytest.mark.asyncio
    async def test_upload_avatar_activates_it_and_resizes_to_square(self, client: AsyncClient):
        user = await create_authenticated_user(
            client, "avatar_upload@test.com", "P@ssw0rd123!", "Avatar", "Upload"
        )
        set_auth_cookies(client, user["cookies"])
        jpeg_bytes = _make_jpeg_bytes(800, 400)

        upload_response = await client.post(
            "/api/v1/users/me/avatar/upload",
            files={"file": ("photo.jpg", jpeg_bytes, "image/jpeg")},
        )

        assert upload_response.status_code == 201
        assert upload_response.json()["is_active"] is True

        user_id = user["user"]["id"]
        image_response = await client.get(f"/api/v1/users/{user_id}/avatar")
        assert image_response.status_code == 200
        served_image = Image.open(io.BytesIO(image_response.content))
        assert served_image.size == (512, 512)

    @pytest.mark.asyncio
    async def test_upload_rejects_non_image_bytes(self, client: AsyncClient):
        user = await create_authenticated_user(
            client, "avatar_invalid@test.com", "P@ssw0rd123!", "Avatar", "Invalid"
        )
        set_auth_cookies(client, user["cookies"])

        response = await client.post(
            "/api/v1/users/me/avatar/upload",
            files={"file": ("not-a-photo.txt", b"hello world", "text/plain")},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_rejects_file_over_size_limit(self, client: AsyncClient):
        user = await create_authenticated_user(
            client, "avatar_toobig@test.com", "P@ssw0rd123!", "Avatar", "TooBig"
        )
        set_auth_cookies(client, user["cookies"])
        oversized_payload = b"x" * (10 * 1024 * 1024 + 1)

        response = await client.post(
            "/api/v1/users/me/avatar/upload",
            files={"file": ("huge.jpg", oversized_payload, "image/jpeg")},
        )

        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_rejects_declared_content_length_over_limit_before_parsing_body(
        self, client: AsyncClient
    ):
        """
        El middleware de Content-Length debe rechazar según lo que el cliente
        DECLARA, sin depender de autenticación ni de parsear el multipart body
        — por eso este test no crea usuario ni hace login.
        """
        request = client.build_request(
            "POST",
            "/api/v1/users/me/avatar/upload",
            content=b"tiny-body-but-lying-about-its-size",
        )
        request.headers["content-length"] = str(10 * 1024 * 1024 + 1)

        response = await client.send(request)

        assert response.status_code == 413


class TestAvatarUploadHistoryAndSwitching:
    @pytest.mark.asyncio
    async def test_switch_between_preset_and_uploaded_history(self, client: AsyncClient):
        user = await create_authenticated_user(
            client, "avatar_history@test.com", "P@ssw0rd123!", "Avatar", "History"
        )
        set_auth_cookies(client, user["cookies"])

        upload_response = await client.post(
            "/api/v1/users/me/avatar/upload",
            files={"file": ("photo.jpg", _make_jpeg_bytes(), "image/jpeg")},
        )
        upload_id = upload_response.json()["id"]

        # Cambiar a un preset: la foto subida sigue en el historial, pero inactiva
        await client.post("/api/v1/users/me/avatar/preset", json={"preset_id": 2})

        uploads_response = await client.get("/api/v1/users/me/avatar/uploads")
        assert uploads_response.status_code == 200
        uploads = uploads_response.json()
        assert len(uploads) == 1
        assert uploads[0]["id"] == upload_id
        assert uploads[0]["is_active"] is False

        # Reactivar la foto subida sin volver a subirla
        activate_response = await client.post(
            f"/api/v1/users/me/avatar/uploads/{upload_id}/activate"
        )
        assert activate_response.status_code == 200
        assert activate_response.json()["avatar_source"] == "UPLOAD"

    @pytest.mark.asyncio
    async def test_remove_avatar_falls_back_to_no_avatar(self, client: AsyncClient):
        user = await create_authenticated_user(
            client, "avatar_remove@test.com", "P@ssw0rd123!", "Avatar", "Remove"
        )
        set_auth_cookies(client, user["cookies"])
        await client.post("/api/v1/users/me/avatar/preset", json={"preset_id": 1})

        remove_response = await client.delete("/api/v1/users/me/avatar")

        assert remove_response.status_code == 200
        assert remove_response.json()["avatar_source"] == "NONE"

        user_id = user["user"]["id"]
        image_response = await client.get(f"/api/v1/users/{user_id}/avatar")
        assert image_response.status_code == 404
