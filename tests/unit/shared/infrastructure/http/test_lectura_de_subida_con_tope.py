"""
La lectura por trozos de una subida corta en cuanto se pasa del tope (F-08).

La comparten la subida del avatar y la de la galería: ninguna de las dos debe
cargar un fichero enorme entero en memoria antes de rechazarlo. Lanza su propio
error, UploadTooLargeError: `shared` no importa de los módulos (revisión de la fase 2),
y cada ruta lo traduce a su 413.
"""

import pytest

from src.shared.infrastructure.http.upload_reader import (
    UploadTooLargeError,
    read_upload_within_limit,
)

pytestmark = pytest.mark.asyncio

MB = 1024 * 1024


class _FicheroQueCuenta:
    """Un UploadFile falso de `tamano` bytes que apunta cuánto se le ha leído."""

    def __init__(self, tamano: int) -> None:
        self._restante = tamano
        self.leido = 0

    async def read(self, size: int = -1) -> bytes:
        """Devuelve hasta `size` bytes (todo lo que queda si es -1)."""
        cuantos = self._restante if size < 0 else min(size, self._restante)
        self._restante -= cuantos
        self.leido += cuantos
        return b"x" * cuantos


async def test_un_fichero_enorme_se_rechaza_sin_leerlo_entero():
    """
    Given: un fichero de 50 MB y un tope de 10 MB
    When: se lee con el tope
    Then: se rechaza, y se ha leído como mucho el tope más un trozo
    """
    fichero = _FicheroQueCuenta(50 * MB)

    with pytest.raises(UploadTooLargeError):
        await read_upload_within_limit(fichero, 10 * MB)  # type: ignore[arg-type]

    assert fichero.leido <= 11 * MB


async def test_un_fichero_de_11_mb_se_rechaza():
    """
    Given: un fichero de 11 MB y un tope de 10 MB
    When: se lee con el tope
    Then: se rechaza
    """
    with pytest.raises(UploadTooLargeError):
        await read_upload_within_limit(_FicheroQueCuenta(11 * MB), 10 * MB)  # type: ignore[arg-type]


async def test_un_fichero_justo_en_el_tope_se_lee_entero():
    """
    Given: un fichero de exactamente 10 MB y un tope de 10 MB
    When: se lee con el tope
    Then: se devuelven sus 10 MB
    """
    datos = await read_upload_within_limit(_FicheroQueCuenta(10 * MB), 10 * MB)  # type: ignore[arg-type]

    assert len(datos) == 10 * MB


async def test_un_fichero_de_9_mb_se_lee_entero():
    """
    Given: un fichero de 9 MB y un tope de 10 MB
    When: se lee con el tope
    Then: se devuelven sus 9 MB
    """
    datos = await read_upload_within_limit(_FicheroQueCuenta(9 * MB), 10 * MB)  # type: ignore[arg-type]

    assert len(datos) == 9 * MB
