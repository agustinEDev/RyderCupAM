"""
HandicapsDeLaCompeticion - El hándicap de cada inscrito, en una consulta (RyderCupAM#251).

Cuál cuenta lo decide la inscripción (`Enrollment.handicap_que_cuenta`); aquí
solo se trae el del perfil de quien no tiene uno propio, y de una vez: la sala
de draft se refresca cada pocos segundos con doce mirando, y una consulta por
jugador es una tormenta de N+1 cada vez.
"""

from collections.abc import Iterable
from decimal import Decimal

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class HandicapsDeLaCompeticion:
    """El hándicap con el que juega cada inscrito, o None si no tiene ninguno."""

    @staticmethod
    async def de(
        enrollments: Iterable[Enrollment],
        user_repository: UserRepositoryInterface,
    ) -> dict[UserId, Decimal | None]:
        """
        Args:
            enrollments: Las inscripciones de quienes interesan
            user_repository: De donde sale el hándicap del perfil

        Returns:
            Cada jugador con el hándicap que le cuenta, en el orden recibido
        """
        inscripciones = list(enrollments)
        sin_propio = [e.user_id for e in inscripciones if e.custom_handicap is None]

        del_perfil: dict[UserId, Decimal] = {}
        if sin_propio:
            for user in await user_repository.find_by_ids(sin_propio):
                if user.id is not None and user.handicap is not None:
                    del_perfil[user.id] = Decimal(str(user.handicap.value))

        return {e.user_id: e.handicap_que_cuenta(del_perfil.get(e.user_id)) for e in inscripciones}
