"""
Las fotos se recodifican sin datos escondidos (S-09, auditoría del 18 nov 2026).

El comentario de un JPEG (segmento COM) sobrevivía a la recodificación del avatar y de la
galería: cualquiera podía esconder lo que quisiera en una foto que se sirve a otros.

  B5-1 un JPEG con comentario, EXIF y perfil de color  -> sale sin ninguno de los tres
  B5-2 la imagen                                        -> igual: tamaño, modo y formato
"""

import io
import struct

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


# --- El perfil de color se aplica antes de quitarlo (/code-review de la PR) -------------
#
# Quitar el perfil sin convertir los píxeles hacía que una foto de iPhone (Display P3) se
# viera como sRGB: desaturada. Para probarlo sin depender de un perfil del sistema, se
# construye un perfil RGB mínimo con los primarios rotados: con la conversión, un píxel
# «rojo» en ese perfil tiene que salir verde en sRGB.


# Primarios de sRGB adaptados a D50 (los que usa un perfil de pantalla ICC v2)
_ROJO = (0.4360747, 0.2225045, 0.0139322)
_VERDE = (0.3850649, 0.7168786, 0.0971045)
_AZUL = (0.1430804, 0.0606169, 0.7141733)
_D50 = (0.9642, 1.0, 0.8249)


def _s15(valor: float) -> bytes:
    return struct.pack(">i", round(valor * 65536))


def _xyz(x: float, y: float, z: float) -> bytes:
    return b"XYZ " + b"\0" * 4 + _s15(x) + _s15(y) + _s15(z)


def _perfil_con_los_colores_rotados() -> bytes:
    curva = b"curv" + b"\0" * 4 + struct.pack(">I", 1) + struct.pack(">H", 0x0233) + b"\0\0"
    etiquetas = [
        (b"wtpt", _xyz(*_D50)),
        # Rotación de tres: el «rojo» del perfil es el verde de sRGB, su «verde» el azul
        # y su «azul» el rojo. Si la conversión se hiciera al revés (de sRGB al perfil),
        # el rojo saldría azul, no verde (CodeRabbit: un cambio de dos es simétrico)
        (b"rXYZ", _xyz(*_VERDE)),
        (b"gXYZ", _xyz(*_AZUL)),
        (b"bXYZ", _xyz(*_ROJO)),
        (b"rTRC", curva),
        (b"gTRC", curva),
        (b"bTRC", curva),
    ]
    inicio = 128 + 4 + 12 * len(etiquetas)
    tabla, datos = b"", b""
    for firma, contenido in etiquetas:
        tabla += firma + struct.pack(">II", inicio + len(datos), len(contenido))
        datos += contenido + b"\0" * (-len(contenido) % 4)
    cuerpo = struct.pack(">I", len(etiquetas)) + tabla + datos
    cabecera = (
        struct.pack(">I", 128 + len(cuerpo))
        + b"lcms"
        + struct.pack(">I", 0x02100000)
        + b"mntrRGB XYZ "
        + b"\0" * 12
        + b"acsp"
        + b"\0" * 24
        + struct.pack(">I", 0)
        + _s15(_D50[0])
        + _s15(_D50[1])
        + _s15(_D50[2])
        + b"\0" * 48
    )
    assert len(cabecera) == 128
    return cabecera + cuerpo


def _roja(perfil: bytes | None) -> bytes:
    imagen = Image.new("RGB", (900, 600), color=(220, 20, 20))
    buffer = io.BytesIO()
    imagen.save(buffer, "JPEG", quality=95, **({"icc_profile": perfil} if perfil else {}))
    return buffer.getvalue()


def _color_del_centro(datos: bytes) -> tuple[int, int, int]:
    imagen = Image.open(io.BytesIO(datos)).convert("RGB")
    return imagen.getpixel((imagen.width // 2, imagen.height // 2))


@pytest.mark.parametrize("proceso", ["process_avatar_image", "process_gallery_image"])
async def test_b5_3_the_colour_profile_is_applied_before_it_is_dropped(proceso):
    """
    Given: Una foto «roja» con un perfil cuyo rojo es el verde de sRGB (y verde→azul, azul→rojo)
    When: Se procesa
    Then: Sale verde y sin perfil: los colores se pasaron a sRGB antes de quitarlo
    """
    resultado = await getattr(PillowImageProcessor(), proceso)(
        _roja(_perfil_con_los_colores_rotados())
    )

    rojo, verde, azul = _color_del_centro(resultado)
    assert verde > rojo + 80 and verde > azul + 80, (rojo, verde, azul)
    assert "icc_profile" not in Image.open(io.BytesIO(resultado)).info


@pytest.mark.parametrize("proceso", ["process_avatar_image", "process_gallery_image"])
async def test_b5_4_without_a_profile_the_colours_do_not_change(proceso):
    """Sin perfil (sRGB por defecto): el rojo sigue siendo rojo."""
    resultado = await getattr(PillowImageProcessor(), proceso)(_roja(None))

    rojo, verde, _ = _color_del_centro(resultado)
    assert rojo > verde + 80, (rojo, verde)


def _perfil_gris_lineal() -> bytes:
    """Un perfil de grises con respuesta lineal (gamma 1): su gris 128 es más claro en sRGB."""
    curva = b"curv" + b"\0" * 4 + struct.pack(">I", 0)  # 0 puntos: identidad (lineal)
    etiquetas = [(b"wtpt", _xyz(*_D50)), (b"kTRC", curva)]
    inicio = 128 + 4 + 12 * len(etiquetas)
    tabla, datos = b"", b""
    for firma, contenido in etiquetas:
        tabla += firma + struct.pack(">II", inicio + len(datos), len(contenido))
        datos += contenido + b"\0" * (-len(contenido) % 4)
    cuerpo = struct.pack(">I", len(etiquetas)) + tabla + datos
    cabecera = (
        struct.pack(">I", 128 + len(cuerpo))
        + b"lcms"
        + struct.pack(">I", 0x02100000)
        + b"mntrGRAYXYZ "
        + b"\0" * 12
        + b"acsp"
        + b"\0" * 24
        + struct.pack(">I", 0)
        + _s15(_D50[0])
        + _s15(_D50[1])
        + _s15(_D50[2])
        + b"\0" * 48
    )
    return cabecera + cuerpo


@pytest.mark.parametrize("proceso", ["process_avatar_image", "process_gallery_image"])
async def test_b5_5_a_grey_picture_with_its_profile_is_converted(proceso):
    """
    Given: Un PNG en grises (modo L) con un perfil de grises lineal
    When: Se procesa
    Then: El gris se corrige a sRGB (128 lineal sale bastante más claro), no se deja igual
          (CodeRabbit: pasarlo a RGB antes hacía fallar la conversión en silencio)
    """
    imagen = Image.new("L", (900, 600), color=128)
    buffer = io.BytesIO()
    imagen.save(buffer, "PNG", icc_profile=_perfil_gris_lineal())

    resultado = await getattr(PillowImageProcessor(), proceso)(buffer.getvalue())

    rojo, verde, azul = _color_del_centro(resultado)
    assert min(rojo, verde, azul) > 170, (rojo, verde, azul)


@pytest.mark.parametrize("proceso", ["process_avatar_image", "process_gallery_image"])
async def test_b5_6_a_text_entry_called_icc_profile_does_not_break(proceso):
    """
    Given: Un PNG válido con un texto llamado «icc_profile» (Pillow lo deja en info como str)
    When: Se procesa
    Then: Sale bien, sin perfil y con sus colores (antes: TypeError sin capturar, un 500)
    """
    from PIL.PngImagePlugin import PngInfo

    datos = PngInfo()
    datos.add_text("icc_profile", "esto no es un perfil")
    imagen = Image.new("RGB", (900, 600), color=(220, 20, 20))
    buffer = io.BytesIO()
    imagen.save(buffer, "PNG", pnginfo=datos)

    resultado = await getattr(PillowImageProcessor(), proceso)(buffer.getvalue())

    rojo, verde, _ = _color_del_centro(resultado)
    assert rojo > verde + 80
