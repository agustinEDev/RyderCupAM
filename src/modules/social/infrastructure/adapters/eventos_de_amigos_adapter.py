"""Adaptador: la llave de una privada que pregunta `competition`, de la Actividad de social."""

from src.modules.competition.application.ports.eventos_de_amigos_interface import (
    EventosDeAmigosInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.social.application.feed_scope import resolve_feed_scope
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class EventosDeAmigosAdapter(EventosDeAmigosInterface):
    """
    Lo que le sale en Actividad de sus amigos, con la misma regla que el feed
    (`resolve_feed_scope`): amigos que publican, tipos que ven los amigos y lo
    no oculto. Sin «se ha apuntado»: el feed no lo enseña de una privada, y la
    llave solo se pide para privadas.
    """

    def __init__(self, social_uow: SocialUnitOfWorkInterface, user_uow: UserUnitOfWorkInterface):
        self._social_uow = social_uow
        self._user_uow = user_uow

    async def amigos_con_evento_en(
        self, user_id: UserId, competition_id: CompetitionId
    ) -> frozenset[UserId]:
        amigos = (await resolve_feed_scope(self._social_uow, self._user_uow, user_id)).friends
        if amigos.is_empty:
            return frozenset()
        trozo = ActivitySlice(
            user_ids=amigos.user_ids,
            types=amigos.types - {ActivityEventType.ENROLLED_IN_TOURNAMENT},
            only_visible_to_friends=True,
        )
        async with self._social_uow:
            autores = await self._social_uow.activity_events.authors_in_competition(
                trozo, str(competition_id.value)
            )
        return frozenset(autores)
