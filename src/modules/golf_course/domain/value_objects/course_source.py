"""
CourseSource Value Object - De dónde salen los datos de un campo.

Distinguir el origen permite reconocer un campo ya importado sin comparar
nombres, y saber si sus datos los avala una federación o los tecleó alguien.
"""

from enum import StrEnum


class CourseSource(StrEnum):
    """
    Origen de los datos de un campo de golf.

    Es un enum y no texto libre para que no acaben conviviendo 'RFEG', 'rfeg' y
    'R.F.E.G.' señalando lo mismo. Cada federación nueva es un valor más.

    - MANUAL: dado de alta por una persona desde la aplicación
    - RFEG: Real Federación Española de Golf
    """

    MANUAL = "MANUAL"
    RFEG = "RFEG"

    def __str__(self) -> str:
        return self.value
