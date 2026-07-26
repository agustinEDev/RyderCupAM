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
