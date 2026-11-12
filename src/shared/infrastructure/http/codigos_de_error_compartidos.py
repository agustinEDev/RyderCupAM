"""
Errores del código compartido que la API traduce a su código HTTP en un solo sitio.

La respuesta es la que daba cada ruta con su `except X: raise HTTPException(código, str(e))`:
el código de aquí y {"detail": str(e)}. Lo registra la composition root
(`src/config/codigos_de_error.py`). Un error que en alguna ruta da otro código, o un texto
propio, se sigue traduciendo en esa ruta.
"""

from fastapi import status

from src.shared.domain.value_objects.country_code import InvalidCountryCodeError
from src.shared.infrastructure.http.upload_reader import UploadTooLargeError

CODIGOS_COMPARTIDOS: dict[type[Exception], int] = {
    # 400: la petición no tiene sentido para el estado o las reglas del juego
    InvalidCountryCodeError: status.HTTP_400_BAD_REQUEST,
    # 413: la subida pasa del tamaño máximo
    UploadTooLargeError: status.HTTP_413_CONTENT_TOO_LARGE,
}
