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
from typing import Protocol, runtime_checkable

from src.modules.competition.domain.value_objects.validation_status import ValidationStatus
from src.modules.user.domain.value_objects.user_id import UserId


@runtime_checkable
class FilaDelHoyo(Protocol):
    """
    Lo que `cuenta` lee de una fila de hoyo: de quién es, qué hoyo y si está validada.

    Es la entidad `HoleScore`; va como Protocol para que un objeto de valor no importe una
    entidad, que a su vez importa objetos de valor (ciclo B10, fase 5).
    """

    @property
    def player_user_id(self) -> UserId:
        """El jugador de la fila."""
        ...

    @property
    def hole_number(self) -> int:
        """El hoyo."""
        ...

    @property
    def validation_status(self) -> ValidationStatus:
        """Si la fila está validada."""
        ...


@dataclass(frozen=True)
class BolasFuera:
    """Los retirados ahora y, de los que volvieron, los hoyos cerrados sin su bola."""

    retirados: frozenset[UserId] = frozenset()
    hoyos_sin_su_bola: Mapping[UserId, frozenset[int]] = field(default_factory=dict)

    def cuenta(self, fila: FilaDelHoyo) -> bool:
        """Si la bola de esta fila cuenta para el resultado del hoyo."""
        if fila.hole_number in self.hoyos_sin_su_bola.get(fila.player_user_id, frozenset()):
            return False
        return not (
            fila.player_user_id in self.retirados
            and fila.validation_status != ValidationStatus.MATCH
        )

    def __bool__(self) -> bool:
        return bool(self.retirados) or any(self.hoyos_sin_su_bola.values())
