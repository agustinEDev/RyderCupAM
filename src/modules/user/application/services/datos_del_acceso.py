"""
Lo que lleva el token de acceso (BE #737).

`sub` es el usuario y `did` el dispositivo desde el que entró. Con `did`, que un
dispositivo esté revocado se comprueba por su id en cada petición, y deja de
depender de una huella de navegador e IP que cambia con cada actualización o red.
"""

CLAIM_DEL_DISPOSITIVO = "did"


def datos_del_acceso(user_id: str, device_id: str | None) -> dict[str, str]:
    """Los datos del token de acceso: el usuario y, si lo hay, su dispositivo."""
    datos = {"sub": user_id}
    if device_id:
        datos[CLAIM_DEL_DISPOSITIVO] = device_id
    return datos
