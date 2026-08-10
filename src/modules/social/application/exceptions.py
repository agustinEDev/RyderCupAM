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
    El jugador pedido no esta: no existe o esta dado de baja.

    **Se traduce a 404.** No cubre el caso de "existe pero no sois amigos": la
    ficha minima de un jugador (nombre, apellidos y foto) la ve cualquier
    usuario registrado, porque los jugadores se buscan por nombre y hay que
    poder reconocer a alguien antes de mandarle una solicitud.
    """

    pass


class ActivityNotVisibleError(Exception):
    """
    La actividad de ese jugador es privada para quien pregunta.

    **Se traduce a 403 y no a 404**, al contrario que el perfil. Aqui un 403 no
    filtra nada: la ficha minima del jugador ya es visible, asi que su
    existencia no es ningun secreto que proteger. Fingir un 404 solo confundiria
    al cliente, que acaba de recibir el perfil de esa misma persona.
    """

    pass
