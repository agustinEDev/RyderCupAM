"""Caso de Uso: El feed de actividad de mis amigos."""

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
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Tope duro por pagina. El cliente puede pedir menos, nunca mas: el feed carga
# los autores de cada pagina, y una pagina enorme seria una consulta enorme.
MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 20


class GetFriendsFeedUseCase:
    """
    Lo que hemos conseguido mis amigos y yo, de lo mas reciente a lo mas antiguo.

    **Uno se ve a si mismo en su propio feed.** Un feed donde no sale lo que
    acabas de hacer se lee como si no se hubiera guardado, y ademas deja el feed
    vacio a quien todavia no tiene amigos. Lo propio se incluye sin mirar el
    interruptor de publicacion: ese decide lo que ven los demas, no lo que uno
    ve de si mismo. El aviso de novedades, en cambio, solo cuenta lo de los
    amigos — los logros de uno no son noticia para uno.

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
    ):
        self._social_uow = social_uow
        self._user_uow = user_uow
        self._golf_course_uow = golf_course_uow

    async def execute(
        self, viewer_id_raw: str, limit: int = DEFAULT_PAGE_SIZE, cursor: str | None = None
    ) -> FeedResponseDTO:
        viewer_id = UserId(viewer_id_raw)
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        before, before_id = parse_cursor(cursor)

        # Las unidades de trabajo se abren en serie, nunca una dentro de otra:
        # comparten sesion por debajo, y el `commit` de la interior cerraria la
        # transaccion que la exterior todavia esta usando
        async with self._social_uow:
            amigos = await self._social_uow.friendships.find_friend_ids(viewer_id)

        de_amigos, visto_hasta = await self._publicables_y_ultima_visita(viewer_id, amigos)

        # El jugador se ve a si mismo en su propio feed, junto a sus amigos: un
        # feed donde no sale lo que uno acaba de hacer se lee como si no se
        # hubiera guardado. Se añade sin mirar su `share_activity`, porque ese
        # interruptor gobierna lo que ven los demas, no lo que uno ve de si mismo
        publicables = [*de_amigos, viewer_id]

        async with self._social_uow:
            eventos = await self._social_uow.activity_events.find_for_users(
                publicables, limit=limit, before=before, before_id=before_id
            )
            # El aviso cuenta solo lo de los amigos: los logros de uno mismo no
            # son novedad para uno. Terminar una partida y que el feed anuncie
            # "3 novedades" que son tuyas seria absurdo
            no_vistos = (
                0
                if visto_hasta is None or not de_amigos
                else await self._social_uow.activity_events.count_for_users_since(
                    de_amigos, since=visto_hasta
                )
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

    async def _publicables_y_ultima_visita(
        self, viewer_id: UserId, amigos: list[UserId]
    ) -> tuple[list[UserId], datetime | None]:
        """
        De mis amigos, los que tienen la publicacion encendida; y cuando mire yo
        el feed por ultima vez.

        Las dos cosas salen del mismo sitio, asi que se resuelven en una sola
        apertura en lugar de dos.

        Apagar la publicacion ya retira lo publicado (BE #175), asi que en la
        practica no deberian quedar eventos suyos. Se filtra igualmente porque
        la regla es "no aparece en el feed de nadie", y no debe depender de que
        el borrado de otro caso de uso haya ido bien.

        `feed_last_seen_at` en None significa que nunca lo ha abierto: entonces
        no hay novedades que contar. Anunciar "247 novedades" a quien entra por
        primera vez no ayuda a nadie.
        """
        if not amigos:
            return [], None

        publicables = []
        async with self._user_uow:
            for amigo in amigos:
                user = await self._user_uow.users.find_by_id(amigo)
                if user is not None and user.is_active and user.share_activity:
                    publicables.append(amigo)

            viewer = await self._user_uow.users.find_by_id(viewer_id)
            visto_hasta = viewer.feed_last_seen_at if viewer else None

        return publicables, visto_hasta

    async def _autores(self, eventos: list[ActivityEvent]) -> dict[str, FeedAuthorDTO]:
        """
        Quien publico cada entrada de esta pagina.

        Van en la respuesta para que pintar el feed no exija una peticion de
        perfil por entrada. Se consulta cada autor una vez aunque aparezca en
        varias entradas.
        """
        ids = {e.user_id for e in eventos}
        if not ids:
            return {}

        autores: dict[str, FeedAuthorDTO] = {}
        async with self._user_uow:
            for user_id in ids:
                user = await self._user_uow.users.find_by_id(user_id)
                if user is None:
                    continue
                autores[str(user_id.value)] = FeedAuthorDTO(
                    id=str(user_id.value),
                    first_name=user.first_name,
                    last_name=user.last_name,
                    avatar_source=user.avatar_source.value,
                    avatar_preset_id=user.avatar_preset_id,
                )
        return autores

    async def _campos(self, eventos: list[ActivityEvent]) -> dict[str, str]:
        """
        Como se llama cada campo citado en esta pagina.

        El `payload` solo guarda el `golf_course_id`, asi que el nombre se
        resuelve al leer. Va en la respuesta por el mismo motivo que los
        autores: pintar el feed no debe costar una peticion por entrada. Se
        consulta cada campo una vez aunque salga en varias.

        Un id que ya no existe se omite en lugar de romper la pagina: el feed
        cuenta un logro, y el logro sigue siendo cierto aunque el campo se haya
        borrado. La entrada se pinta sin el nombre.
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
                campo = await self._golf_course_uow.golf_courses.find_by_id(GolfCourseId(course_id))
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
            payload=evento.payload,
            source_match_id=evento.source_match_id,
        )
