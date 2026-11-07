"""Errores del cambio de correo pendiente (#749, revisión)."""


class EmailChangeInvalidError(ValueError):
    """No hay ese cambio pendiente: otro token, uno ya usado, o anulado."""


class EmailChangeExpiredError(ValueError):
    """El cambio pendiente caducó (24 horas): se anula y hay que pedirlo de nuevo."""


class EmailChangeEmailInUseError(ValueError):
    """El correo pendiente lo tiene ya otra cuenta: el cambio no se hace."""
