"""Errores de aplicación del módulo de campos de golf (mapa de hoyos, BE #532)."""


class HoleMapNotFoundError(Exception):
    """El campo no tiene mapa (o no uno que se pueda enseñar)."""


class HoleMapChangedError(Exception):
    """El admin revisaba otra versión: el mapa se reimportó entretanto."""


class GolfCourseNotFoundError(Exception):
    """No hay ningún campo con ese id."""


class HoleNotInCourseError(Exception):
    """No hay ese hoyo en una vuelta: solo del 1 al 18 (un campo de 9 se juega dos veces)."""


class HoleAlreadyMappedError(Exception):
    """El hoyo ya tiene salida y green en el mapa aprobado: no hay nada que marcar."""


class TeeRequiredError(Exception):
    """El hoyo no tiene salida que vean los jugadores: la marca tiene que traerla."""
