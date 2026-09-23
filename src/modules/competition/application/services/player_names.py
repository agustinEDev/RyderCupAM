"""
PlayerNames - El nombre con el que se pinta a cada jugador (BE #254).

`display_name` por defecto —el alias de quien lo tenga y el nombre completo de
quien no (BE #239)—, salvo que la inscripcion de esa persona en ESTA
competicion haya elegido el nombre legal (BE #254).

De golpe para todos: una consulta de usuarios y una de inscripciones. La vista
de anotacion resuelve lo mismo de uno en uno y a proposito —son 2-4 jugadores y
comparte `AsyncSession`, ver su comentario—, asi que esa no pasa por aqui.
"""

from collections.abc import Sequence

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class PlayerNames:
    """Quien se llama como, dentro de una competicion."""

    @staticmethod
    async def de_la_competicion(
        user_ids: Sequence[UserId],
        competition_id: CompetitionId,
        user_repository: UserRepositoryInterface,
        uow: CompetitionUnitOfWorkInterface,
    ) -> dict[UserId, str]:
        """
        Args:
            user_ids: Solo de quien se vaya a pintar, no toda la competicion:
                las inscripciones acumulan sin limite rechazos, retiros y altas
                de nuevo, y traerlas todas costaba una consulta por pagina
            competition_id: Donde se mira, que la preferencia es por competicion
            user_repository: De donde salen los nombres
            uow: Para leer que inscripcion pidio el nombre legal

        Returns:
            user_id -> nombre, con cadena vacia para quien no se encuentre
        """
        if not user_ids:
            return {}
        users = await user_repository.find_by_ids(list(user_ids))
        enrollments = await uow.enrollments.find_by_user_ids_and_competition(
            list(user_ids), competition_id
        )
        real_name_wanted = {e.user_id for e in enrollments if e.use_real_name}
        names: dict[UserId, str] = {
            user.id: user.display_name_or_legal(user.id in real_name_wanted)
            for user in users
            if user.id is not None
        }
        return {uid: names.get(uid, "") for uid in user_ids}
