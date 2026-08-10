"""
Tests del procesado de fotos de galeria con Pillow (BE #177).

La diferencia con el avatar es toda la razon de que exista un metodo aparte: la
galeria **no recorta a cuadrado**, porque una foto de una vuelta suele ser
apaisada y el recorte central se comeria medio campo.
"""

import io

import pytest
from PIL import Image

from src.modules.user.domain.errors.user_errors import InvalidAvatarImageError
from src.modules.user.infrastructure.external.pillow_image_processor import (
    GALLERY_MAX_SIDE,
    PillowImageProcessor,
)


def _jpeg(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (34, 139, 34)).save(buffer, "JPEG")
    return buffer.getvalue()


@pytest.fixture
def processor():
    return PillowImageProcessor()


def test_conserva_la_proporcion_de_una_foto_apaisada(processor):
    """Given una foto 4:3 / When se procesa / Then sigue siendo 4:3, no un cuadrado."""
    resultado = processor.process_gallery_image(_jpeg(4000, 3000))

    ancho, alto = Image.open(io.BytesIO(resultado)).size
    assert (ancho, alto) == (GALLERY_MAX_SIDE, 810)
    assert ancho != alto


def test_conserva_la_proporcion_de_una_foto_vertical(processor):
    """Given una foto vertical / When se procesa / Then el lado mayor es el alto."""
    resultado = processor.process_gallery_image(_jpeg(1500, 3000))

    ancho, alto = Image.open(io.BytesIO(resultado)).size
    assert alto == GALLERY_MAX_SIDE
    assert ancho < alto


def test_no_amplia_una_foto_que_ya_es_pequena(processor):
    """
    Given una foto menor que el limite / When se procesa / Then se deja igual:
    ampliarla no añadiria detalle, solo peso.
    """
    resultado = processor.process_gallery_image(_jpeg(400, 300))

    assert Image.open(io.BytesIO(resultado)).size == (400, 300)


def test_el_avatar_si_recorta_a_cuadrado(processor):
    """Given la misma foto apaisada / When se procesa como avatar / Then sale cuadrada."""
    resultado = processor.process_avatar_image(_jpeg(4000, 3000))

    ancho, alto = Image.open(io.BytesIO(resultado)).size
    assert ancho == alto


def test_la_salida_siempre_es_jpeg(processor):
    """Given un PNG / When se procesa / Then sale JPEG, que es lo que se guarda."""
    buffer = io.BytesIO()
    Image.new("RGB", (800, 600), (10, 20, 30)).save(buffer, "PNG")

    resultado = processor.process_gallery_image(buffer.getvalue())

    assert Image.open(io.BytesIO(resultado)).format == "JPEG"


def test_rechaza_lo_que_no_es_una_imagen(processor):
    """Given un archivo cualquiera / When se procesa / Then se rechaza."""
    with pytest.raises(InvalidAvatarImageError):
        processor.process_gallery_image(b"esto no es una imagen")


def test_rechaza_un_formato_no_admitido(processor):
    """Given un GIF / When se procesa / Then se rechaza: solo JPEG, PNG y WEBP."""
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100)).save(buffer, "GIF")

    with pytest.raises(InvalidAvatarImageError):
        processor.process_gallery_image(buffer.getvalue())


def test_una_foto_de_movil_pesa_lo_previsto(processor):
    """
    Given una foto de 12 megapixeles / When se procesa / Then queda por debajo
    del medio mega que asume el calculo de espacio de la issue.
    """
    resultado = processor.process_gallery_image(_jpeg(4032, 3024))

    assert len(resultado) < 500 * 1024
