"""Errores de aplicación del módulo de campos de golf (mapa de hoyos, BE #532)."""


class HoleMapNotFoundError(Exception):
    """El campo no tiene mapa (o no uno que se pueda enseñar)."""


class HoleMapChangedError(Exception):
    """El admin revisaba otra versión: el mapa se reimportó entretanto."""


class GolfCourseNotFoundError(Exception):
    """No hay ningún campo con ese id."""


class HoleNotInCourseError(Exception):
    """No hay ese hoyo en una vuelta: solo del 1 al 18 (un campo de 9 se juega dos veces)."""


class HoleSampleNotFoundError(Exception):
    """La muestra no existe en ese campo (BE #575)."""


class HoleReportNotFoundError(Exception):
    """El reporte no existe en ese campo (entrega 7)."""


class InvalidHoleLineError(Exception):
    """La línea que el admin quiere guardar no vale: codos, distancias o puntos (BE #575)."""


class GolfCourseMissingError(Exception):
    """
    No está el campo que se pide: el campo, la propuesta de cambio (clon) o su original.

    La API lo traduce a 404 en el mapa de errores del módulo. No hereda de ValueError:
    el `except ValueError` de una ruta lo convertiría en un 400.
    """


class CountryNotFoundError(ValueError):
    """No hay ningún país con ese código. Al editar se responde 404; al crear, 400."""


class GolfCourseEditForbiddenError(Exception):
    """Quien edita el campo no es su creador ni admin (403)."""
