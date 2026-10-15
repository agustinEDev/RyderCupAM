"""Errores de aplicación del módulo de campos de golf (mapa de hoyos, BE #532)."""


class HoleMapNotFoundError(Exception):
    """El campo no tiene mapa (o no uno que se pueda enseñar)."""


class HoleMapChangedError(Exception):
    """El admin revisaba otra versión: el mapa se reimportó entretanto."""
