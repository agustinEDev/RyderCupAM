"""
Las dos rutas que reciben imágenes traducen el error de la lectura con tope
(UploadTooLargeError, de shared) a su 413 (revisión de la fase 2, 9 nov 2026).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.modules.social.infrastructure.api.v1 import profile_photo_routes
from src.modules.user.infrastructure.api.v1 import avatar_routes

pytestmark = pytest.mark.asyncio

MB = 1024 * 1024


class _Fichero:
    """Un UploadFile falso de 11 MB."""

    def __init__(self) -> None:
        self._restante = 11 * MB

    async def read(self, size: int = -1) -> bytes:
        """Devuelve hasta `size` bytes."""
        cuantos = self._restante if size < 0 else min(size, self._restante)
        self._restante -= cuantos
        return b"x" * cuantos


def _peticion() -> Request:
    """Una petición cualquiera (la pide el limitador)."""
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/x",
            "query_string": b"",
            "headers": [],
            "client": ("1.2.3.4", 1),
        }
    )


async def test_the_avatar_upload_turns_a_too_large_file_into_413():
    """
    Given: Un fichero de 11 MB para el avatar (tope 10 MB)
    When: Llega a la ruta
    Then: 413, sin llegar al caso de uso
    """
    caso = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await avatar_routes.upload_avatar(
            _peticion(), current_user=SimpleNamespace(id=uuid4()), file=_Fichero(), use_case=caso
        )

    assert error.value.status_code == 413
    caso.execute.assert_not_awaited()


async def test_the_gallery_upload_turns_a_too_large_file_into_413():
    """
    Given: Un fichero de 11 MB para la galería (tope 10 MB)
    When: Llega a la ruta
    Then: 413, sin llegar al caso de uso
    """
    caso = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await profile_photo_routes.upload_my_photo(
            _peticion(),
            file=_Fichero(),
            caption=None,
            current_user=SimpleNamespace(id=uuid4()),
            use_case=caso,
        )

    assert error.value.status_code == 413
    caso.execute.assert_not_awaited()
