"""
El correo con el que una cuenta casa las invitaciones enviadas a una dirección (F-07).

Una invitación se puede mandar a un correo que aún no tiene cuenta. Quien se
registrara con esa dirección sin demostrar que es suya la veía, la aceptaba y
entraba en una competición privada. Desde la fase 3 del plan a 9 (10 nov 2026)
solo casa el correo VERIFICADO: sin verificar, la invitación a esa dirección no
existe para esa cuenta (ni en la lista, ni al responder, ni para ver la
competición o sus inscritos). Las dirigidas a la cuenta (por user_id) no cambian.
"""


def correo_del_invitado(email: str | None, verificado: bool) -> str | None:
    """El correo que casa invitaciones: el suyo si está verificado; si no, ninguno."""
    return email if verificado and email else None
