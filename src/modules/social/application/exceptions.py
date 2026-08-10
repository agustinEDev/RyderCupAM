"""Excepciones compartidas de la capa de aplicacion del modulo Social."""


class FriendshipNotFoundError(Exception):
    """La relacion de amistad no existe."""

    pass


class AddresseeNotFoundError(Exception):
    """El usuario destinatario (addressee_id) no existe."""

    pass


class NotFriendshipParticipantError(Exception):
    """El usuario no participa en esta relacion de amistad."""

    pass


class NotAddresseeError(Exception):
    """El usuario no es el destinatario de la solicitud de amistad."""

    pass


class ProfileNotVisibleError(Exception):
    """
    El perfil pedido no es visible para quien pregunta.

    **Se traduce a 404, nunca a 403.** Un 403 diria "existe, pero no puedes
    verlo", que es justo lo que no debe saberse: convertiria el endpoint en un
    detector de cuentas, donde probar identificadores distingue las que existen
    de las que no. Para quien no es amigo, el perfil sencillamente no esta.

    Por eso tampoco distingue entre "no existe esa cuenta" y "existe pero no
    sois amigos": las dos situaciones producen esta misma excepcion.
    """

    pass
