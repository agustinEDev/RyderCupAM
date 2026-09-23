"""
DraftRoster - Los jugadores que entran al draft, con su handicap (FE #653).

El handicap que cuenta es el de la inscripcion si tiene uno propio, y si no el
del jugador; sin ninguno, cero. Esa regla ya estaba dentro del reparto
automatico, y el draft necesita exactamente la misma: si divergieran, la
aplicacion elegiria por un capitan con un criterio distinto del que usa al
repartir sola.

Los capitanes no entran: nombrarlos ya los fijo en su equipo (RyderCupAm#320).
"""

from collections.abc import Iterable
from decimal import Decimal

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.services.snake_draft_service import PlayerForDraft
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class DraftRoster:
    """Quien puede ser elegido, y con que handicap."""

    @staticmethod
    async def de_los_inscritos(
        enrollments: Iterable[Enrollment],
        user_repository: UserRepositoryInterface,
        excluidos: Iterable[UserId] = (),
    ) -> list[PlayerForDraft]:
        """
        Args:
            enrollments: Las inscripciones aprobadas
            user_repository: De donde sale el handicap del jugador
            excluidos: Quien no entra al draft, normalmente los dos capitanes

        Returns:
            Los jugadores con su handicap, en el orden de las inscripciones
        """
        fuera = set(excluidos)
        entran = [e for e in enrollments if e.user_id not in fuera]

        # Una sola consulta para todos los que no traen handicap propio: la
        # sala se refresca cada pocos segundos y la miran doce a la vez, asi que
        # una consulta por jugador aqui es una tormenta de N+1 cada vez
        sin_handicap_propio = [e.user_id for e in entran if e.custom_handicap is None]
        del_perfil = {}
        if sin_handicap_propio:
            for user in await user_repository.find_by_ids(sin_handicap_propio):
                if user.id is not None and user.handicap is not None:
                    del_perfil[user.id] = Decimal(str(user.handicap.value))

        return [
            PlayerForDraft(
                user_id=e.user_id,
                handicap=e.custom_handicap
                if e.custom_handicap is not None
                else del_perfil.get(e.user_id, Decimal("0")),
            )
            for e in entran
        ]
