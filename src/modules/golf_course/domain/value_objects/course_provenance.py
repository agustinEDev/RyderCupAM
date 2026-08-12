"""
CourseProvenance Value Object - De dónde vienen los datos de un campo.

Sirve para reconocer un campo ya importado sin tener que comparar nombres, que
es frágil: basta con que un admin renombre un campo para que la siguiente
importación lo duplique.
"""

from dataclasses import dataclass
from datetime import datetime

from .course_source import CourseSource

MAX_EXTERNAL_ID_LENGTH = 100


@dataclass(frozen=True)
class CourseProvenance:
    """
    Procedencia de los datos de un campo.

    Business Rules:
    - Un campo dado de alta a mano no tiene identificador externo ni fecha de
      importación: esos datos solo los pone un importador.
    - Un campo importado sí lleva fecha, porque es lo que permite saber si sus
      datos se contrastaron con la fuente hace un mes o hace tres años.
    - El identificador externo es opcional aunque el origen no sea manual: no
      todas las federaciones publican un id estable por recorrido.
    """

    source: CourseSource = CourseSource.MANUAL
    external_id: str | None = None
    imported_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.external_id is not None:
            cleaned = self.external_id.strip()
            object.__setattr__(self, "external_id", cleaned or None)
            if cleaned and len(cleaned) > MAX_EXTERNAL_ID_LENGTH:
                raise ValueError(
                    f"External id must be at most {MAX_EXTERNAL_ID_LENGTH} characters, "
                    f"got {len(cleaned)}"
                )

        if self.source is CourseSource.MANUAL:
            if self.external_id is not None:
                raise ValueError("A manually created course cannot have an external id")
            if self.imported_at is not None:
                raise ValueError("A manually created course cannot have an import date")
        elif self.imported_at is None:
            raise ValueError(f"An imported course ({self.source}) needs an import date")

    @property
    def is_imported(self) -> bool:
        """True si los datos vienen de una fuente externa."""
        return self.source is not CourseSource.MANUAL
