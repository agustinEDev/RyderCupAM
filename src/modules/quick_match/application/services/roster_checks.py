"""
Comprobaciones de la plantilla de una partida rápida, compartidas.

Crear paso a paso, añadir un amigo, iniciar y crear e iniciar de una vez
(FE #848) piden lo mismo al campo, a los usuarios y a las amistades: aquí
viven una vez, para que una regla nueva no se aplique en un camino y en el
otro no.
"""

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.quick_match.application.exceptions import (
    FriendUserNotFoundError,
    GolfCourseNotApprovedError,
    GolfCourseNotFoundError,
    InvalidTeeSelectionError,
    NotFriendsError,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender

Tee = tuple[TeeColor | None, Gender | None]


async def check_course_and_tees(
    golf_course_uow: GolfCourseUnitOfWorkInterface,
    golf_course_id: GolfCourseId,
    tees: list[Tee],
) -> GolfCourse:
    """
    El campo existe, está aprobado y tiene cada barra elegida.

    Sin barra (color nulo) no hay nada que comprobar: es opcional.
    """
    async with golf_course_uow:
        golf_course = await golf_course_uow.golf_courses.find_by_id(golf_course_id)
    if not golf_course:
        raise GolfCourseNotFoundError(f"Golf course not found: {golf_course_id.value}")
    if golf_course.approval_status != ApprovalStatus.APPROVED:
        raise GolfCourseNotApprovedError(f"Golf course '{golf_course.name}' is not approved.")
    for color, gender in tees:
        if color is not None and not golf_course.has_tee(color, gender):
            raise InvalidTeeSelectionError(
                f"{color.value} is not a valid tee for this golf course."
            )
    return golf_course


async def check_friends(
    user_uow: UserUnitOfWorkInterface,
    social_uow: SocialUnitOfWorkInterface,
    requester_id: UserId,
    friend_ids: list[UserId],
) -> None:
    """Cada amigo existe (si no, 404) y es amigo ACEPTADO de quien lo añade (si no, 403)."""
    async with user_uow:
        users = await user_uow.users.find_by_ids(friend_ids)
    found = {user.id for user in users}
    for friend_id in friend_ids:
        if friend_id not in found:
            raise FriendUserNotFoundError(f"User not found: {friend_id.value}")
    async with social_uow:
        for friend_id in friend_ids:
            if not await social_uow.friendships.are_friends(requester_id, friend_id):
                raise NotFriendsError(
                    "Only accepted friends can be added directly to a quick match."
                )


async def profile_handicaps(
    user_uow: UserUnitOfWorkInterface, user_ids: list[UserId]
) -> dict[UserId, float | None]:
    """
    El hándicap del perfil de cada usuario, en una sola consulta.

    Sin `async with user_uow`: comparte la sesión de la petición y su salida
    hace commit, que partía «empezar» en dos —la partida quedaba en juego y sin
    fijar, y soltaba el bloqueo de su fila— (revisión de la BE #514; es el
    patrón de la BE #497). Se puede leer dentro de la transacción de la
    partida sin cerrarla.
    """
    users = await user_uow.users.find_by_ids(user_ids)
    return {
        user.id: (user.handicap.value if user.handicap else None)
        for user in users
        if user.id is not None
    }


async def check_tee_of_match(
    quick_match_uow: QuickMatchUnitOfWorkInterface,
    golf_course_uow: GolfCourseUnitOfWorkInterface,
    quick_match_id: QuickMatchId,
    requester_id: UserId,
    tee: Tee,
) -> None:
    """
    La barra elegida existe en el campo de la partida, al añadir a alguien.

    Se mira ANTES de abrir la transacción que bloquea la partida: dentro, el
    `async with` del campo hacía commit a mitad sobre la sesión compartida y
    soltaba el bloqueo. Solo para su creador —a otro le toca el 403 de
    siempre—, y un campo que ya no está es una barra que no vale, como antes.
    """
    color, gender = tee
    if color is None:
        return
    async with quick_match_uow:
        quick_match = await quick_match_uow.quick_matches.find_by_id(quick_match_id)
    if quick_match is None or quick_match.creator_id != requester_id:
        return
    async with golf_course_uow:
        golf_course = await golf_course_uow.golf_courses.find_by_id(quick_match.golf_course_id)
    if not golf_course or not golf_course.has_tee(color, gender):
        raise InvalidTeeSelectionError(f"{color.value} is not a valid tee for this golf course.")
