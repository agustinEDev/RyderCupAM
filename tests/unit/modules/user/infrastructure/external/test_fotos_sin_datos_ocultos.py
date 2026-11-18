"""
Las fotos se recodifican sin datos escondidos (S-09, auditoría del 18 nov 2026).

El comentario de un JPEG (segmento COM) sobrevivía a la recodificación del avatar y de la
galería: cualquiera podía esconder lo que quisiera en una foto que se sirve a otros.

  B5-1 un JPEG con comentario, EXIF y perfil de color  -> sale sin ninguno de los tres
  B5-2 la imagen                                        -> igual: tamaño, modo y formato
"""

import io

import pytest
from PIL import Image

from src.modules.user.infrastructure.external.pillow_image_processor import (
    AVATAR_TARGET_SIZE,
    PillowImageProcessor,
)

pytestmark = pytest.mark.asyncio

ESCONDIDO = b"<script>alert(1)</script>"


def _jpeg_con_datos_ocultos(ancho: int = 900, alto: int = 600) -> bytes:
    imagen = Image.new("RGB", (ancho, alto), color=(10, 120, 200))
    exif = Image.Exif()
    exif[0x010E] = "descripcion escondida"  # ImageDescription
    buffer = io.BytesIO()
    imagen.save(buffer, "JPEG", comment=ESCONDIDO, exif=exif, icc_profile=b"perfil-de-color")
    datos = buffer.getvalue()
    assert ESCONDIDO in datos  # la foto de partida sí los lleva
    return datos


@pytest.mark.parametrize("proceso", ["process_avatar_image", "process_gallery_image"])
async def test_b5_1_the_output_has_no_comment_exif_or_icc(proceso):
    """
    Given: Un JPEG con comentario, EXIF y perfil de color
    When: Se procesa como avatar o como foto de galería
    Then: El resultado no lleva ninguno de los tres
    """
    resultado = await getattr(PillowImageProcessor(), proceso)(_jpeg_con_datos_ocultos())

    assert ESCONDIDO not in resultado
    assert b"descripcion escondida" not in resultado
    salida = Image.open(io.BytesIO(resultado))
    assert "comment" not in salida.info
    assert "exif" not in salida.info
    assert "icc_profile" not in salida.info


@pytest.mark.parametrize(
    ("proceso", "tamano"),
    [
        ("process_avatar_image", (AVATAR_TARGET_SIZE, AVATAR_TARGET_SIZE)),
        ("process_gallery_image", (900, 600)),
    ],
)
async def test_b5_2_the_picture_itself_is_unchanged(proceso, tamano):
    """
    Given: El mismo JPEG
    When: Se procesa
    Then: JPEG en RGB del tamaño de siempre
    """
    resultado = await getattr(PillowImageProcessor(), proceso)(_jpeg_con_datos_ocultos())

    salida = Image.open(io.BytesIO(resultado))
    assert (salida.format, salida.mode, salida.size) == ("JPEG", "RGB", tamano)
