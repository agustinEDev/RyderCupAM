"""
A quien y a que campo se refiere una pagina de actividad.

Vive aparte porque lo comparten el feed de amigos y la actividad de un jugador:
las dos pintan las mismas tarjetas, y quien sale con nombre —el autor, sus
rivales y compañeros— tiene que seguir la misma regla de privacidad en las dos.
Dos copias se separarian en cuanto una cambiara, y la que se quedara atras
enseñaria a quien no debe.
"""

from collections.abc import Sequence

from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.social.application.dto.profile_dto import FeedAuthorDTO
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import InvalidUserIdError, UserId


async def autores_de(
    social_uow: SocialUnitOfWorkInterface,
    user_uow: UserUnitOfWorkInterface,
    eventos: Sequence[ActivityEvent],
    viewer_id: UserId,
    otros: Sequence[UserId] | None = None,
) -> dict[str, FeedAuthorDTO]:
    """
    Quien publico cada entrada de esta pagina, y las demas personas que
    nombra: rivales y compañeros de un resultado, quien pide amistad.

    Van en la respuesta para que pintar la pagina no exija una peticion de
    perfil por entrada. Se leen todos de una vez, no uno por autor.

    **De los nombrados solo vienen los que quien mira puede ver**: nadie
    con quien tenga un bloqueo, lo pusiera quien lo pusiera, ni una cuenta
    desactivada. Sin sus datos, el cliente pinta «un jugador».
    """
    propios = {e.user_id for e in eventos} | set(otros or [])
    nombrados: set[UserId] = set()
    for evento in eventos:
        nombrados.update(nombrados_en(evento.payload))
    nombrados -= propios
    if nombrados:
        async with social_uow:
            nombrados -= set(await social_uow.friendships.find_blocked_ids(viewer_id))
    ids = propios | nombrados
    if not ids:
        return {}

    async with user_uow:
        usuarios = [
            u for u in await user_uow.users.find_by_ids(list(ids)) if u.id in propios or u.is_active
        ]

    return {
        str(user.id.value): FeedAuthorDTO(
            id=str(user.id.value),
            first_name=user.first_name,
            last_name=user.last_name,
            display_name=user.display_name,
            avatar_source=user.avatar_source.value,
            avatar_preset_id=user.avatar_preset_id,
        )
        for user in usuarios
    }


async def campos_de(
    golf_course_uow: GolfCourseUnitOfWorkInterface, eventos: Sequence[ActivityEvent]
) -> dict[str, str]:
    """
    Como se llama cada campo citado en esta pagina.

    El `payload` solo guarda el `golf_course_id`, asi que el nombre se
    resuelve al leer. Va en la respuesta por el mismo motivo que los
    autores: pintar la pagina no debe costar una peticion por entrada. Se
    leen todos los nombres en una sola consulta, aunque un campo salga en
    varias entradas.

    Un id que no se puede resolver se omite en lugar de romper la pagina: la
    entrada cuenta un logro, y el logro sigue siendo cierto aunque el campo se
    haya borrado. La entrada se pinta sin el nombre. Eso vale igual para un
    campo que ya no existe que para un id ilegible — el `payload` es JSONB y
    nada garantiza su forma anos despues de haberse escrito, asi que un
    valor con el que no se puede ni construir un `GolfCourseId` no puede
    costar la peticion entera.
    """
    legibles: dict[str, GolfCourseId] = {}
    for evento in eventos:
        crudo = evento.payload.get("golf_course_id")
        if not isinstance(crudo, str) or crudo in legibles:
            continue
        try:
            legibles[crudo] = GolfCourseId(crudo)
        except ValueError:
            continue
    if not legibles:
        return {}

    async with golf_course_uow:
        nombres = await golf_course_uow.golf_courses.find_names_by_ids(list(legibles.values()))
    # La clave es el id tal y como viene en el `payload`: es con el que el
    # cliente lo busca
    return {
        crudo: nombres[str(identificador.value)]
        for crudo, identificador in legibles.items()
        if str(identificador.value) in nombres
    }


def nombrados_en(payload: dict) -> set[UserId]:
    """
    Los jugadores con cuenta que nombra un resultado: `opponent_ids` y
    `partner_ids` en los de torneo, `opponents` y `partners` en los de partida
    rapida (el invitado va por su nombre). Lo ilegible se ignora: el `payload`
    es JSONB y nada garantiza su forma con los años.
    """
    crudos: list = []
    for clave in ("opponent_ids", "partner_ids"):
        valor = payload.get(clave)
        if isinstance(valor, list):
            crudos.extend(valor)
    for clave in ("opponents", "partners"):
        valor = payload.get(clave)
        if isinstance(valor, list):
            crudos.extend(p.get("user_id") for p in valor if isinstance(p, dict))

    nombrados = set()
    for crudo in crudos:
        if not crudo:
            continue
        try:
            nombrados.add(UserId(crudo))
        except (TypeError, ValueError, InvalidUserIdError):
            continue
    return nombrados
