"""
Las bolas que no cuentan en un fourball con retirados (Agustín, 25 oct 2026).

Del retirado cuentan sus hoyos marcados y confirmados (validados) al retirarlo;
los demás no, y nadie puede validarlos después. Si se deshace la retirada, los
hoyos que se cerraron sin su bola mientras estuvo fuera se quedan así: su bola
solo vuelve en los que aún no se habían cerrado.

Va en un solo objeto, y no en listas sueltas por cada función de la regla:
quien calcula el resultado de un hoyo pide `match.bolas_fuera` y no puede
olvidarse de una de las dos mitades (code-review).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.value_objects.validation_status import ValidationStatus
from src.modules.user.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class BolasFuera:
    """Los retirados ahora y, de los que volvieron, los hoyos cerrados sin su bola."""

    retirados: frozenset[UserId] = frozenset()
    hoyos_sin_su_bola: Mapping[UserId, frozenset[int]] = field(default_factory=dict)

    def cuenta(self, fila: HoleScore) -> bool:
        """Si la bola de esta fila cuenta para el resultado del hoyo."""
        if fila.hole_number in self.hoyos_sin_su_bola.get(fila.player_user_id, frozenset()):
            return False
        return not (
            fila.player_user_id in self.retirados
            and fila.validation_status != ValidationStatus.MATCH
        )

    def __bool__(self) -> bool:
        return bool(self.retirados) or any(self.hoyos_sin_su_bola.values())
