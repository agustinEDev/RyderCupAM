"""
El tope de 10 MB de la galería se aplica antes de cargar la foto entera (F-08).

La subida de fotos de la galería leía el fichero entero con `await file.read()`
y solo después comprobaba su tamaño: un fichero enorme llegaba completo a
memoria antes de rechazarse. Ahora se comporta como la del avatar: la cabecera
Content-Length se mira en un middleware antes de parsear el cuerpo, y el
endpoint lee por trozos y corta en cuanto se pasa del tope.
"""

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from src.config.dependencies import get_current_user, get_upload_profile_photo_use_case
from src.modules.social.application.dto.profile_photo_dto import ProfilePhotoDTO
from src.modules.social.application.use_cases.upload_profile_photo_use_case import (
    MAX_UPLOAD_BYTES,
)

pytestmark = pytest.mark.asyncio

USUARIO = "3f2b8c1e-9d4a-4e7b-8a2f-1c5d6e7f8a9b"
MB = 1024 * 1024
RUTA = "/api/v1/users/me/photos"


class _UsuarioFalso:
    """Lo único que la ruta lee del usuario actual: su id."""

    id = USUARIO


class _CasoDeUsoQueApunta:
    """Caso de uso falso que apunta cuántos bytes le llegan, sin mirar el tamaño."""

    def __init__(self) -> None:
        self.recibidos: list[int] = []

    async def execute(
        self, user_id_raw: str, raw_bytes: bytes, caption: str | None = None
    ) -> ProfilePhotoDTO:
        """Apunta el tamaño recibido y devuelve una foto cualquiera."""
        self.recibidos.append(len(raw_bytes))
        return ProfilePhotoDTO(
            id="foto",
            user_id=user_id_raw,
            caption=caption,
            created_at=datetime.now(UTC),
            url="/foto",
        )


@pytest.fixture
def caso_de_uso() -> Iterator[_CasoDeUsoQueApunta]:
    """La app real con el usuario y el caso de uso sustituidos."""
    falso = _CasoDeUsoQueApunta()
    app.dependency_overrides[get_current_user] = _UsuarioFalso
    app.dependency_overrides[get_upload_profile_photo_use_case] = lambda: falso
    try:
        yield falso
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_upload_profile_photo_use_case, None)


def _cuerpo_multipart(tamano: int) -> tuple[bytes, str]:
    """Un multipart con un único fichero `file` de `tamano` bytes."""
    frontera = "fronteradeprueba"
    cuerpo = (
        (
            f"--{frontera}\r\n"
            'Content-Disposition: form-data; name="file"; filename="foto.jpg"\r\n'
            "Content-Type: image/jpeg\r\n\r\n"
        ).encode()
        + b"x" * tamano
        + f"\r\n--{frontera}--\r\n".encode()
    )
    return cuerpo, f"multipart/form-data; boundary={frontera}"


async def _post(cuerpo, content_type: str):
    """POST a la ruta de la galería por la app real."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        return await cliente.post(RUTA, content=cuerpo, headers={"content-type": content_type})


async def test_una_foto_de_11_mb_es_un_413_sin_llegar_al_caso_de_uso(caso_de_uso):
    """
    Given: una foto de 11 MB, que declara su tamaño en Content-Length
    When: se sube a la galería
    Then: 413, y el caso de uso no la recibe
    """
    cuerpo, tipo = _cuerpo_multipart(11 * MB)

    respuesta = await _post(cuerpo, tipo)

    assert respuesta.status_code == 413
    assert caso_de_uso.recibidos == []


async def test_un_content_length_de_11_mb_se_rechaza_sin_leer_el_cuerpo(caso_de_uso):
    """
    Given: una petición que DECLARA 11 MB en Content-Length con un cuerpo diminuto
    When: se sube a la galería
    Then: 413 por la cabecera, antes de parsear el cuerpo (que no es ni un multipart)
    """
    cuerpo = b"cuerpo-pequeno-que-miente-sobre-su-tamano"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        peticion = cliente.build_request(
            "POST", RUTA, content=cuerpo, headers={"content-type": "multipart/form-data"}
        )
        peticion.headers["content-length"] = str(11 * MB)
        respuesta = await cliente.send(peticion)

    assert respuesta.status_code == 413
    assert caso_de_uso.recibidos == []


async def test_una_foto_de_11_mb_sin_content_length_la_corta_el_endpoint(caso_de_uso):
    """
    Given: una foto de 11 MB enviada por trozos, sin Content-Length que mirar
    When: se sube a la galería
    Then: 413 desde la lectura por trozos del endpoint; el caso de uso no la recibe
    """
    cuerpo, tipo = _cuerpo_multipart(11 * MB)

    async def por_trozos() -> AsyncIterator[bytes]:
        for inicio in range(0, len(cuerpo), MB):
            yield cuerpo[inicio : inicio + MB]

    respuesta = await _post(por_trozos(), tipo)

    assert respuesta.status_code == 413
    assert caso_de_uso.recibidos == []


async def test_una_foto_de_9_mb_pasa_entera_al_caso_de_uso(caso_de_uso):
    """
    Given: una foto de 9 MB, por debajo del tope
    When: se sube a la galería
    Then: 201, y el caso de uso la recibe entera
    """
    cuerpo, tipo = _cuerpo_multipart(9 * MB)

    respuesta = await _post(cuerpo, tipo)

    assert respuesta.status_code == 201
    assert caso_de_uso.recibidos == [9 * MB]


async def test_una_foto_justo_en_el_tope_pasa(caso_de_uso):
    """
    Given: una foto de exactamente 10 MB, el tope
    When: se sube a la galería
    Then: pasa: el margen del middleware cubre el framing del multipart
    """
    cuerpo, tipo = _cuerpo_multipart(MAX_UPLOAD_BYTES)

    respuesta = await _post(cuerpo, tipo)

    assert respuesta.status_code == 201
    assert caso_de_uso.recibidos == [MAX_UPLOAD_BYTES]
