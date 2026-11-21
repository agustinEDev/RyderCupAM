"""
BarrasDelCampo - Los cambios de barras de un campo de una competición (20 nov 2026).

Decidido con Agustín: cada inscripción tiene su barra general, y en cada campo
puede haber dos cambios que la pisan:

- R1, el cambio propio de un jugador para ese campo;
- R2, la barra que el organizador fija en ese campo para todos los de un género
  (no pisa un cambio propio).

Sin ninguno, cuenta la general (R3). Que el campo la tenga o no lo decide
`barra_en_el_campo`: si no la tiene, no se elige otra sola (R4).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


@dataclass(frozen=True)
class BarrasDelCampo:
    """
    Atributos:
        propias: El cambio propio de cada jugador en este campo (R1)
        por_genero: La barra fijada para todos los de un género en este campo (R2)
    """

    propias: Mapping[UserId, TeeColor] = field(default_factory=dict)
    por_genero: Mapping[Gender, TeeColor] = field(default_factory=dict)

    def color_de(
        self, user_id: UserId, general: TeeColor | None, genero: Gender | None
    ) -> TeeColor | None:
        """
        El color que juega en este campo: su cambio propio, si no la del campo para
        su género, si no su general (None: la habitual de su género).
        """
        if user_id in self.propias:
            return self.propias[user_id]
        if genero is not None and genero in self.por_genero:
            return self.por_genero[genero]
        return general


SIN_CAMBIOS = BarrasDelCampo()
