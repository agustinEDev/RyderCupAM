"""Caso de Uso: La actividad publicada por un jugador."""

from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.social.application.dto.profile_dto import ActivityEventDTO, FeedResponseDTO
from src.modules.social.application.exceptions import (
    ActivityNotVisibleError,
    ProfileNotVisibleError,
)
from src.modules.social.application.feed_cursor import (
    build_cursor,
    parse_cursor,
    sin_partir_tarjetas,
)
from src.modules.social.application.feed_references import autores_de, campos_de
from src.modules.social.application.feed_scope import payload_for
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
from src.modules.social.application.use_cases.get_friends_feed_use_case import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
)
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.domain.value_objects.activity_audience import (
    types_seen_by_author,
    types_seen_by_friends,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class GetPlayerActivityUseCase:
    """
    Los logros de un jugador concreto, visibles solo entre amigos.

    A diferencia del perfil —cuya ficha minima ve cualquiera—, la actividad es
    **solo para amigos**: es de lo que trata el componente social. Quien no lo
    sea recibe un 403 y no un 404, porque la existencia del jugador ya no es
    ningun secreto: acaba de poder ver su ficha.

    Y la misma regla de publicacion: con el interruptor apagado no hay actividad
    que enseñar, ni siquiera a un amigo.

    Reutiliza el paginado del feed en vez de repetirlo — es el mismo cursor
    sobre los mismos eventos, solo que de un autor en lugar de varios.
    """

    def __init__(
        self,
        social_uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
        tournaments: TournamentVisibilityInterface | None = None,
        invitations: InvitationAvailabilityInterface | None = None,
    ):
        self._social_uow = social_uow
        self._tournaments = tournaments
        self._invitations = invitations
        self._user_uow = user_uow
        self._golf_course_uow = golf_course_uow

    async def execute(
        self,
        viewer_id_raw: str,
        target_id_raw: str,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> FeedResponseDTO:
        viewer_id = UserId(viewer_id_raw)
        target_id = UserId(target_id_raw)
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        before, before_id = parse_cursor(cursor)

        async with self._user_uow:
            target = await self._user_uow.users.find_by_id(target_id)
            if target is None or not target.is_active:
                raise ProfileNotVisibleError("Profile not found")
            publica = target.share_activity

        if viewer_id != target_id:
            async with self._social_uow:
                if not await self._social_uow.friendships.are_friends(viewer_id, target_id):
                    raise ActivityNotVisibleError("Only friends can see this player's activity")

        # El interruptor apagado no es un error: el perfil existe y es visible,
        # simplemente no tiene actividad publicada.
        #
        # No se aplica a uno mismo. El interruptor gobierna lo que ven los demas,
        # no lo que uno ve de si mismo — es la misma regla que ya sigue el feed,
        # donde los logros propios salen tenga el interruptor como lo tenga.
        # Sin esta excepcion, apagarlo dejaria al jugador sin poder consultar su
        # propio historial.
        if not publica and viewer_id != target_id:
            return FeedResponseDTO()

        # Cada uno ve de si mismo lo SELF y lo BOTH, como en su feed; sus amigos,
        # lo FRIENDS y lo BOTH que no publico con la publicacion apagada
        if viewer_id == target_id:
            trozo = ActivitySlice(user_ids=(target_id,), types=types_seen_by_author())
        else:
            trozo = ActivitySlice(
                user_ids=(target_id,),
                types=types_seen_by_friends(),
                only_visible_to_friends=True,
            )

        async with self._social_uow:
            eventos = await self._social_uow.activity_events.find_in(
                [trozo], limit=limit, before=before, before_id=before_id
            )
            # Ninguna tarjeta partida entre dos paginas, como en el feed
            eventos = await sin_partir_tarjetas(
                self._social_uow.activity_events, [trozo], eventos, limit
            )

        # Como en el feed: el cursor antes de ocultar los apuntados a torneos
        # que ahora son privados (E, 22 oct)
        siguiente = build_cursor(eventos, limit)
        eventos = await sin_apuntados_a_privados(eventos, self._tournaments)
        eventos = await sin_invitaciones_cerradas(eventos, self._invitations)

        # Quien sale con nombre y en que campo, con la misma regla que el feed:
        # son las mismas tarjetas, y el perfil no puede enseñar a quien el feed
        # oculta. Sin esto el cliente pinta al dueño y a sus rivales como «un
        # jugador»
        autores = await autores_de(self._social_uow, self._user_uow, eventos, viewer_id)
        campos = await campos_de(self._golf_course_uow, eventos)

        return FeedResponseDTO(
            authors=autores,
            courses=campos,
            events=[
                ActivityEventDTO(
                    id=str(e.id),
                    user_id=str(e.user_id.value),
                    type=e.type.value,
                    occurred_at=e.occurred_at,
                    published_at=e.published_at,
                    payload=payload_for(e, viewer_id),
                    source_match_id=e.source_match_id,
                    group_key=e.card_key,
                )
                for e in eventos
            ],
            next_cursor=siguiente,
        )
