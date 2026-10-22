"""Caso de Uso: El feed de actividad de mis amigos."""

from collections.abc import Callable
from datetime import datetime

from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.social.application.dto.profile_dto import (
    ActivityEventDTO,
    FeedResponseDTO,
    FriendRequestNoticeDTO,
)
from src.modules.social.application.feed_cursor import (
    build_cursor,
    parse_cursor,
    sin_partir_tarjetas,
)
from src.modules.social.application.feed_references import autores_de, campos_de
from src.modules.social.application.feed_scope import (
    count_unseen,
    payload_for,
    pending_requests,
    resolve_feed_scope,
)
from src.modules.social.application.feed_visibility import (
    sin_apuntados_a_privados,
    sin_invitaciones_cerradas,
)
from src.modules.social.application.ports.invitation_availability_interface import (
    InvitationAvailabilityInterface,
)
from src.modules.social.application.ports.tournament_visibility_interface import (
    TournamentVisibilityInterface,
)
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.entities.friendship import Friendship
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
    de producto): anuncia todo lo nuevo de Actividad, con tope de 99.

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
        tournaments: TournamentVisibilityInterface | None = None,
        invitations: InvitationAvailabilityInterface | None = None,
    ):
        self._social_uow = social_uow
        self._tournaments = tournaments
        self._invitations = invitations
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
            # Ninguna tarjeta partida entre dos paginas
            eventos = await sin_partir_tarjetas(
                self._social_uow.activity_events, scope.slices, eventos, limit
            )
            # Las solicitudes de amistad y el mismo recuento que da `GET
            # /users/me/feed/unseen-count`: el numero del boton y el de la
            # pantalla no pueden discrepar. Solo en la primera pagina: las
            # siguientes no los pintan
            solicitudes: list[Friendship] = []
            no_vistos = 0
            if before is None:
                solicitudes = await pending_requests(self._social_uow.friendships, viewer_id)
                no_vistos = await count_unseen(self._social_uow.activity_events, scope, solicitudes)

        # El cursor, con la pagina tal cual se leyo: si se oculta algo, la
        # pagina queda corta pero no se pierde ni se repite nada (E, 22 oct)
        siguiente = build_cursor(eventos, limit)
        eventos = await sin_apuntados_a_privados(eventos, self._tournaments)
        eventos = await sin_invitaciones_cerradas(eventos, self._invitations)

        autores = await autores_de(
            self._social_uow,
            self._user_uow,
            eventos,
            viewer_id,
            [s.requester_id for s in solicitudes],
        )
        campos = await campos_de(self._golf_course_uow, eventos)

        return FeedResponseDTO(
            events=[self._a_dto(e, viewer_id) for e in eventos],
            authors=autores,
            courses=campos,
            next_cursor=siguiente,
            unseen_count=no_vistos,
            pending_friend_requests=[
                FriendRequestNoticeDTO(
                    friendship_id=str(s.id.value),
                    requester=autores[str(s.requester_id.value)],
                    created_at=s.created_at,
                )
                for s in solicitudes
                # Sin su cuenta no hay a quien aceptar
                if str(s.requester_id.value) in autores
            ],
        )

    @staticmethod
    def _a_dto(evento: ActivityEvent, viewer_id: UserId) -> ActivityEventDTO:
        return ActivityEventDTO(
            id=str(evento.id),
            user_id=str(evento.user_id.value),
            type=evento.type.value,
            occurred_at=evento.occurred_at,
            published_at=evento.published_at,
            payload=payload_for(evento, viewer_id),
            source_match_id=evento.source_match_id,
            group_key=evento.card_key,
        )
