"""
Lo que lleva el token de acceso (BE #737).

`sub` es el usuario y `did` el dispositivo desde el que entró. Con `did`, que un
dispositivo esté revocado se comprueba por su id en cada petición, y deja de
depender de una huella de navegador e IP que cambia con cada actualización o red.
"""

CLAIM_DEL_DISPOSITIVO = "did"


def datos_del_acceso(user_id: str, device_id: str) -> dict[str, str]:
    """Los datos del token de acceso: el usuario y su dispositivo (toda sesión tiene uno)."""
    return {"sub": user_id, CLAIM_DEL_DISPOSITIVO: device_id}
