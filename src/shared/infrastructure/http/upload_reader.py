"""
Lectura por trozos de un fichero subido, con tope de tamaño.

La comparten las rutas que reciben imágenes (avatar y galería del perfil), para
que ninguna cargue un fichero enorme entero en memoria antes de rechazarlo.
"""

from fastapi import UploadFile

from src.modules.user.domain.errors.user_errors import AvatarUploadTooLargeError

_UPLOAD_READ_CHUNK_BYTES = 1024 * 1024  # 1 MB


async def read_upload_within_limit(file: UploadFile, max_bytes: int) -> bytes:
    """
    Lee un UploadFile por trozos, cortando en cuanto se supera `max_bytes`.

    A diferencia de `await file.read()` (que carga el cuerpo entero en memoria
    antes de que nadie pueda comprobar su tamaño), esto evita que un archivo
    absurdamente grande llegue a bufferizarse por completo: el rechazo por
    tamaño ocurre tan pronto como se cruza el límite, no después.

    Raises:
        AvatarUploadTooLargeError: si el fichero pasa de `max_bytes`.
    """
    buffer = bytearray()
    while True:
        chunk = await file.read(_UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise AvatarUploadTooLargeError(
                f"El archivo supera el tamaño máximo permitido ({max_bytes // (1024 * 1024)}MB)"
            )
    return bytes(buffer)
