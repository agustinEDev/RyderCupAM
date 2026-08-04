"""Caso de Uso: Borrado definitivo de una cuenta de usuario (panel de administración)."""

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.exceptions import UserHasActivityException
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class AdminDeleteUserUseCase:
    """
    Borra definitivamente la cuenta de un usuario (solo Admin).

    Bloquea el borrado si la cuenta tiene actividad de la que dependen otros
    usuarios o que rompería una restriccion de la base de datos:
    - Ha creado alguna competicion (competitions.creator_id es ON DELETE CASCADE:
      borraria el torneo entero para todos sus participantes).
    - Ha creado alguna partida rapida (mismo motivo, quick_matches.creator_id CASCADE).
    - Ha solicitado algun campo de golf (golf_courses.creator_id sin ON DELETE: fallaria).
    - Tiene algun hole score registrado (hole_scores.player_user_id es ON DELETE
      CASCADE, pero borrarlos falsearia el resultado del partido para sus rivales).

    En esos casos, el panel de administracion debe ofrecer "Desactivar" en su lugar
    (ver AdminSetUserActiveUseCase).

    Las invitaciones NO bloquean: ambas FKs de `invitations` hacia `users` son
    ON DELETE CASCADE (migracion c7d1e4f8a2b6), asi que las invitaciones enviadas
    y recibidas por la cuenta desaparecen con ella. Bloquear ahi dejaria al admin
    sin salida, porque no existe forma de borrar invitaciones ajenas.
    """

    def __init__(
        self,
        user_uow: UserUnitOfWorkInterface,
        competition_uow: CompetitionUnitOfWorkInterface,
        quick_match_uow: QuickMatchUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
    ):
        self._user_uow = user_uow
        self._competition_uow = competition_uow
        self._quick_match_uow = quick_match_uow
        self._golf_course_uow = golf_course_uow

    async def execute(self, user_id_str: str) -> None:
        user_id = UserId(user_id_str)

        async with self._user_uow:
            user = await self._user_uow.users.find_by_id(user_id)
            if not user:
                raise UserNotFoundError(f"User not found: {user_id_str}")

        reasons = await self._collect_activity_reasons(user_id)
        if reasons:
            raise UserHasActivityException(reasons)

        async with self._user_uow:
            await self._user_uow.users.delete_by_id(user_id)

    async def _collect_activity_reasons(self, user_id: UserId) -> list[str]:
        reasons: list[str] = []

        async with self._competition_uow:
            competitions_created = await self._competition_uow.competitions.count_by_creator(
                user_id
            )
            if competitions_created > 0:
                reasons.append(f"has created {competitions_created} competition(s)")

            has_scores = await self._competition_uow.hole_scores.exists_by_player(user_id)
            if has_scores:
                reasons.append("has recorded hole scores in one or more matches")

        async with self._quick_match_uow:
            if await self._quick_match_uow.quick_matches.exists_created_by(user_id):
                reasons.append("has created one or more quick matches")

        async with self._golf_course_uow:
            golf_courses_requested = await self._golf_course_uow.golf_courses.count_by_creator(
                user_id
            )
            if golf_courses_requested > 0:
                reasons.append(f"has requested {golf_courses_requested} golf course(s)")

        return reasons
