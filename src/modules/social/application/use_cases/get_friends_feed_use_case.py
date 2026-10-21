"""Caso de Uso: El feed de actividad de mis amigos."""

from collections.abc import Callable
from datetime import datetime

from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.social.application.dto.profile_dto import (
    ActivityEventDTO,
    FeedAuthorDTO,
    FeedResponseDTO,
)
from src.modules.social.application.feed_cursor import build_cursor, parse_cursor
from src.modules.social.application.feed_scope import count_unseen, resolve_feed_scope
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.utc_clock import utc_now

# Tope duro por pagina. El cliente puede pedir menos, nunca mas: el feed carga
# los autores de cada pagina, y una pagina enorme seria una consulta enorme.
MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 20


class GetFriendsFeedUseCase:
    """
    Lo que hemos conseguido mis amigos y yo, de lo mas reciente a lo mas antiguo.

    **Cada tipo de evento tiene su publico** (`ActivityAudience`): de lo mio
    veo lo SELF y lo BOTH; de mis amigos, lo FRIENDS y lo BOTH que publicaron
    con la publicacion encendida.

    **Uno se ve a si mismo en su propio feed.** Un feed donde no sale lo que
    acabas de hacer se lee como si no se hubiera guardado, y ademas deja el feed
    vacio a quien todavia no tiene amigos. Lo propio se incluye sin mirar el
    interruptor de publicacion: ese decide lo que ven los demas, no lo que uno
    ve de si mismo. El aviso de novedades cuenta tambien lo propio (decision
    de producto): anuncia todo lo nuevo de Actividad, con tope de 10.

    **El feed se lee, no se escribe** (fan-out on read): al pedirlo se consultan
    los eventos de mis amigos. No hay una copia por amigo creada al publicar.
    Con el tamaño de esta aplicacion es la opcion correcta y con diferencia la
    mas simple; repartir en escritura solo compensa con miles de seguidores por
    cuenta y trae duplicacion y reconciliacion cada vez que alguien acepta o
    deshace una amistad.

    **La privacidad se aplica antes de paginar, no despues.** Quien tiene la
    publicacion apagada se descarta de la lista de autores *antes* de consultar,
    de modo que el limite de la pagina se aplica ya sobre lo que se puede
    enseñar. Filtrar despues devolveria paginas de tamaño irregular —una de 20,
    la siguiente de 14— y obligaria al cliente a adivinar si quedan mas.
    """

    def __init__(
        self,
        social_uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
        reloj: Callable[[], datetime] = utc_now,
    ):
        self._social_uow = social_uow
        self._user_uow = user_uow
        self._golf_course_uow = golf_course_uow
        self._reloj = reloj

    async def execute(
        self, viewer_id_raw: str, limit: int = DEFAULT_PAGE_SIZE, cursor: str | None = None
    ) -> FeedResponseDTO:
        viewer_id = UserId(viewer_id_raw)
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        before, before_id = parse_cursor(cursor)

        scope = await resolve_feed_scope(self._social_uow, self._user_uow, viewer_id, self._reloj)

        # Los dos trozos en una sola consulta: la pagina y el cursor cuadran
        async with self._social_uow:
            eventos = await self._social_uow.activity_events.find_in(
                scope.slices, limit=limit, before=before, before_id=before_id
            )
            # El mismo recuento que da `GET /users/me/feed/unseen-count`: el
            # numero del boton y el de la pantalla no pueden discrepar. Solo en
            # la primera pagina: las siguientes no lo pintan
            no_vistos = (
                await count_unseen(self._social_uow.activity_events, scope) if before is None else 0
            )

        autores = await self._autores(eventos)
        campos = await self._campos(eventos)

        return FeedResponseDTO(
            events=[self._a_dto(e) for e in eventos],
            authors=autores,
            courses=campos,
            next_cursor=build_cursor(eventos, limit),
            unseen_count=no_vistos,
        )

    async def _autores(self, eventos: list[ActivityEvent]) -> dict[str, FeedAuthorDTO]:
        """
        Quien publico cada entrada de esta pagina.

        Van en la respuesta para que pintar el feed no exija una peticion de
        perfil por entrada. Se leen todos de una vez, no uno por autor.
        """
        ids = {e.user_id for e in eventos}
        if not ids:
            return {}

        async with self._user_uow:
            usuarios = await self._user_uow.users.find_by_ids(list(ids))

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

    async def _campos(self, eventos: list[ActivityEvent]) -> dict[str, str]:
        """
        Como se llama cada campo citado en esta pagina.

        El `payload` solo guarda el `golf_course_id`, asi que el nombre se
        resuelve al leer. Va en la respuesta por el mismo motivo que los
        autores: pintar el feed no debe costar una peticion por entrada. Se
        consulta cada campo una vez aunque salga en varias.

        Un id que no se puede resolver se omite en lugar de romper la pagina: el
        feed cuenta un logro, y el logro sigue siendo cierto aunque el campo se
        haya borrado. La entrada se pinta sin el nombre. Eso vale igual para un
        campo que ya no existe que para un id ilegible — el `payload` es JSONB y
        nada garantiza su forma anos despues de haberse escrito, asi que un
        valor con el que no se puede ni construir un `GolfCourseId` no puede
        costar la peticion entera.
        """
        ids = {
            evento.payload["golf_course_id"]
            for evento in eventos
            if evento.payload.get("golf_course_id")
        }
        if not ids:
            return {}

        campos: dict[str, str] = {}
        async with self._golf_course_uow:
            for course_id in ids:
                try:
                    identificador = GolfCourseId(course_id)
                except ValueError:
                    continue
                campo = await self._golf_course_uow.golf_courses.find_by_id(identificador)
                if campo is not None:
                    campos[course_id] = campo.name
        return campos

    @staticmethod
    def _a_dto(evento: ActivityEvent) -> ActivityEventDTO:
        return ActivityEventDTO(
            id=str(evento.id),
            user_id=str(evento.user_id.value),
            type=evento.type.value,
            occurred_at=evento.occurred_at,
            published_at=evento.published_at,
            payload=evento.payload,
            source_match_id=evento.source_match_id,
        )
