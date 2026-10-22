"""Excepciones compartidas de la capa de aplicacion del modulo QuickMatch."""


class QuickMatchNotFoundError(Exception):
    """La partida rapida no existe."""

    pass


class GolfCourseNotFoundError(Exception):
    """El campo de golf indicado no existe."""

    pass


class GolfCourseNotApprovedError(Exception):
    """El campo de golf indicado no esta aprobado."""

    pass


class InvalidTeeSelectionError(Exception):
    """El tee (categoria/genero) elegido no existe en el campo de golf de la partida."""

    pass


class FriendUserNotFoundError(Exception):
    """El usuario a añadir como amigo no existe."""

    pass


class NotFriendsError(Exception):
    """Solo se puede añadir directamente a usuarios con amistad ACCEPTED."""

    pass


class NotQuickMatchCreatorError(Exception):
    """Solo el creador de la partida puede realizar esta accion."""

    pass


class NotAuthorizedToRemoveError(Exception):
    """Solo el creador o el propio participante pueden eliminarlo de la partida."""

    pass


class NotQuickMatchParticipantError(Exception):
    """El usuario no es participante de esta partida rapida."""

    pass


class TargetParticipantNotFoundError(Exception):
    """El participante objetivo no existe en esta partida rapida."""

    pass


class NotAScorerError(Exception):
    """El usuario no esta configurado como anotador de esta partida."""

    pass


class InvalidParticipantError(Exception):
    """Un jugador que no se puede construir (un invitado con el nombre en blanco)."""

    pass


class QuickMatchIdTakenError(Exception):
    """El id que manda el cliente ya es de una partida de otro creador (FE #848)."""

    pass


class QuickMatchNotSharedError(Exception):
    """
    Quien mira no puede ver esta partida de un amigo (bloque K): no es amigo de
    nadie que la comparta, o la partida no esta terminada.
    """

    pass
