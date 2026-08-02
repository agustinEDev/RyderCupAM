"""User Has Activity Exception - Bloquea el borrado definitivo de cuentas con datos."""


class UserHasActivityException(Exception):  # noqa: N818 - Exception is intentional naming
    """
    Lanzada al intentar borrar definitivamente una cuenta que tiene datos
    de los que depende otra gente (torneos creados, partidas rápidas creadas,
    campos de golf solicitados, o historial de scores).

    Borrar sin este chequeo podría:
    - Borrar en cascada torneos/partidas rápidas de OTROS participantes
      (competitions.creator_id y quick_matches.creator_id son ON DELETE CASCADE).
    - Fallar con un IntegrityError de base de datos (hole_scores.player_user_id
      no tiene ON DELETE definido).

    Attributes:
        reasons: Lista de motivos legibles por los que se bloquea el borrado.
    """

    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        message = "Cannot permanently delete this account: " + "; ".join(reasons)
        super().__init__(message)
