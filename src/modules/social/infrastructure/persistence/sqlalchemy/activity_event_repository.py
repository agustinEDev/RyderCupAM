"""Activity Event Repository - SQLAlchemy Implementation."""

from collections.abc import Collection, Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    Delete,
    String,
    and_,
    case,
    cast,
    column,
    delete,
    exists,
    func,
    not_,
    or_,
    select,
    table,
    text,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    insert as pg_insert,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivityEventRepositoryInterface,
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.persistence.mappers.activity_event_mapper import (
    activity_events_table,
    withdrawn_hidden_achievements_table,
    withdrawn_tee_time_notices_table,
)
from src.modules.user.domain.value_objects.user_id import UserId

UQ_ACTIVITY_EVENTS_MATCH_TYPE = "uq_activity_events_match_type"


class SQLAlchemyActivityEventRepository(ActivityEventRepositoryInterface):
    """Implementacion asincrona del repositorio de eventos de actividad."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add_many(self, events: list[ActivityEvent]) -> None:
        """
        Publica los eventos de una vuelta, ignorando los que ya estuvieran.

        Se inserta con ON CONFLICT DO NOTHING en lugar de comprobar antes y
        escribir despues. La comprobacion previa deja una ventana entre el "no
        existe" y el INSERT, y dos peticiones que terminan la misma partida a la
        vez —el movil reintentando sobre una conexion mala es el caso tipico—
        caerian dentro de ella. Dejar que decida la clave unica cierra esa
        ventana sin bloquear nada.

        No pasa por la sesion de la ORM a proposito: `session.add_all()` no
        admite ON CONFLICT, y aqui el evento ya nace completo y no se vuelve a
        tocar, asi que no se pierde nada por no tenerlo en el identity map.

        Un logro que se retiro oculto vuelve oculto (`_volver_a_ocultar`).
        """
        if not events:
            return
        await self._volver_a_ocultar(events)

        filas = [
            {
                "id": event.id,
                "user_id": event.user_id,
                "type": event.type,
                "occurred_at": event.occurred_at,
                "published_at": event.published_at,
                "visible_to_friends": event.visible_to_friends,
                "payload": event.payload,
                "source_match_id": event.source_match_id,
            }
            for event in events
        ]

        stmt = pg_insert(activity_events_table).values(filas)
        await self._session.execute(
            stmt.on_conflict_do_nothing(constraint=UQ_ACTIVITY_EVENTS_MATCH_TYPE)
        )

    async def _volver_a_ocultar(self, events: list[ActivityEvent]) -> None:
        """
        Oculta los logros que se retiraron ocultos y gasta su apunte: desde
        aqui, lo oculto lo guarda el propio logro. Si el alta se salta por la
        clave unica, el logro que ya estaba se queda como estaba.
        """
        claves = [(e.user_id, e.type, e.source_match_id) for e in events if e.type.is_achievement]
        if not claves:
            return
        apuntes = withdrawn_hidden_achievements_table.c
        gastados = (
            await self._session.execute(
                delete(withdrawn_hidden_achievements_table)
                .where(tuple_(apuntes.user_id, apuntes.type, apuntes.source_match_id).in_(claves))
                .returning(apuntes.user_id, apuntes.type, apuntes.source_match_id)
            )
        ).all()
        ocultos = {(f.user_id, f.type, f.source_match_id) for f in gastados}
        for event in events:
            if (event.user_id, event.type, event.source_match_id) in ocultos:
                event.hide_from_friends()

    async def _borrar(self, stmt: Delete) -> int:
        """
        Borra y apunta los logros ocultos que se van: si se vuelven a publicar,
        vuelven ocultos (fallo del probador, 23 oct 2026). Los avisos no se
        apuntan: apuntarse otra vez a un torneo es un aviso nuevo.
        """
        tabla = activity_events_table.c
        filas = (
            await self._session.execute(
                stmt.returning(
                    tabla.user_id, tabla.type, tabla.source_match_id, tabla.visible_to_friends
                )
            )
        ).all()
        ocultos = [
            {"user_id": f.user_id, "type": f.type, "source_match_id": f.source_match_id}
            for f in filas
            if not f.visible_to_friends and f.type.is_achievement
        ]
        if ocultos:
            await self._session.execute(
                pg_insert(withdrawn_hidden_achievements_table)
                .values(ocultos)
                .on_conflict_do_nothing()
            )
        return len(filas)

    async def find_in(
        self,
        slices: Sequence[ActivitySlice],
        limit: int,
        before: datetime | None = None,
        before_id: UUID | None = None,
    ) -> list[ActivityEvent]:
        condicion = self._condicion(slices)
        if condicion is None:
            return []
        return await self._pagina(condicion, limit, before=before, before_id=before_id)

    async def count_in(
        self,
        slices: Sequence[ActivitySlice],
        since: datetime | None,
        cap: int | None = None,
        skip_private_enrollments: bool = False,
        open_invitations_at: datetime | None = None,
        hide_trashed_quick_matches_from: UserId | None = None,
    ) -> int:
        condicion = self._condicion(slices)
        if condicion is None:
            return 0
        if skip_private_enrollments:
            condicion = and_(condicion, not_(self._apuntado_a_privado()))
        if open_invitations_at is not None:
            condicion = and_(condicion, not_(self._invitacion_cerrada(open_invitations_at)))
        if hide_trashed_quick_matches_from is not None:
            condicion = and_(
                condicion,
                not_(self._en_la_papelera_de_otro(hide_trashed_quick_matches_from)),
            )

        # Una fila por tarjeta: los logros de una vuelta de un jugador comparten
        # tarjeta (`ActivityEvent.card_key`); cada aviso va en la suya
        tabla = activity_events_table.c
        logros = sorted(t for t in ActivityEventType if t.is_achievement)
        tarjeta = case(
            (
                tabla.type.in_(logros),
                func.concat(cast(tabla.user_id, String), ":", tabla.source_match_id),
            ),
            else_=cast(tabla.id, String),
        )
        filas = select(tarjeta).where(condicion).distinct()
        if since is not None:
            filas = filas.where(activity_events_table.c.published_at > since)
        if cap is not None:
            # Se cuenta sobre un LIMIT: pasado el tope el numero ya no cambia
            # nada en la pantalla, y asi no se recorre el historial entero
            filas = filas.limit(cap)

        stmt = select(func.count()).select_from(filas.subquery())
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    @staticmethod
    def _en_la_papelera_de_otro(viewer_id: UserId) -> ColumnElement[bool]:
        """
        Lo de otro que salio de una partida rapida que el tiene en su papelera
        (`ActivityEvent.comes_from_a_quick_match`): su origen es el id de la
        partida y su autor esta en `hidden_by_participant_ids`, donde un
        jugador con cuenta va con el id de su usuario. Como con los torneos, se
        mira la tabla `quick_matches` por su nombre y el id como texto.
        """
        tabla = activity_events_table.c
        partidas = table("quick_matches", column("id"), column("hidden_by_participant_ids", JSONB))
        tipos = sorted(t for t in ActivityEventType if t.may_come_from_a_quick_match)
        return and_(
            tabla.user_id != viewer_id,
            tabla.type.in_(tipos),
            tabla.payload["from_tournament"].astext.is_distinct_from("true"),
            exists().where(
                cast(partidas.c.id, String) == tabla.source_match_id,
                partidas.c.hidden_by_participant_ids.op("@>")(
                    func.jsonb_build_array(cast(tabla.user_id, String))
                ),
            ),
        )

    @staticmethod
    def _invitacion_cerrada(ahora: datetime) -> ColumnElement[bool]:
        """
        Un INVITED_TO_TOURNAMENT cuya invitacion (su origen) ya no se puede
        aceptar en `ahora`: no hay una PENDING sin caducar con ese id. Como con
        los torneos, se mira la tabla `invitations` por su nombre y el id como
        texto.
        """
        tabla = activity_events_table.c
        invitaciones = table("invitations", column("id"), column("status"), column("expires_at"))
        return and_(
            tabla.type == ActivityEventType.INVITED_TO_TOURNAMENT,
            not_(
                exists().where(
                    cast(invitaciones.c.id, String) == tabla.source_match_id,
                    invitaciones.c.status == "PENDING",
                    invitaciones.c.expires_at > ahora,
                )
            ),
        )

    @staticmethod
    def _apuntado_a_privado() -> ColumnElement[bool]:
        """
        Un ENROLLED_IN_TOURNAMENT de un torneo que ahora no es publico (regla E).

        Se mira la tabla `competitions` por su nombre, sin importar el modulo de
        competicion: es una lectura de dos columnas dentro de la misma consulta
        del contador, y solo se evalua en las filas de ese tipo. El id va como
        texto porque el del `payload` es texto y un valor ilegible no puede
        tumbar la consulta con un cast a UUID.
        """
        tabla = activity_events_table.c
        competiciones = table("competitions", column("id"), column("visibility"))
        return and_(
            tabla.type == ActivityEventType.ENROLLED_IN_TOURNAMENT,
            exists().where(
                cast(competiciones.c.id, String) == tabla.payload["competition_id"].astext,
                competiciones.c.visibility != "PUBLIC",
            ),
        )

    @staticmethod
    def _condicion(slices: Sequence[ActivitySlice]) -> ColumnElement[bool] | None:
        """
        El WHERE de varios trozos: un OR de (jugadores y tipos), con la
        visibilidad cuando el trozo es de amigos. None si no queda ninguno.
        """
        partes = []
        for trozo in slices:
            if trozo.is_empty:
                continue
            parte = and_(
                activity_events_table.c.user_id.in_(trozo.user_ids),
                activity_events_table.c.type.in_(sorted(trozo.types)),
            )
            if trozo.only_visible_to_friends:
                parte = and_(parte, activity_events_table.c.visible_to_friends.is_(True))
            partes.append(parte)
        return or_(*partes) if partes else None

    async def _pagina(
        self,
        condicion: ColumnElement[bool],
        limit: int,
        before: datetime | None,
        before_id: UUID | None,
    ) -> list[ActivityEvent]:
        stmt = select(ActivityEvent).where(condicion)
        if before is not None:
            # El cursor compara el par entero, no solo la fecha. Todos los
            # eventos de una misma vuelta comparten `published_at` al
            # microsegundo —se publican juntos— asi que filtrar por fecha
            # estricta tiraria tambien los que aun no se han enseñado, y
            # filtrar por `<=` repetiria los ya vistos. El par (fecha, id) si es
            # unico, y `id` desempata de forma estable entre paginas.
            #
            # Un cursor de antes de `published_at` llevaba `occurred_at`: las
            # filas de entonces se rellenaron con esa misma fecha, asi que sigue
            # cayendo en su sitio
            if before_id is not None:
                stmt = stmt.where(
                    tuple_(ActivityEvent._published_at, ActivityEvent._id)
                    < tuple_(before, before_id)
                )
            else:
                stmt = stmt.where(ActivityEvent._published_at < before)

        stmt = stmt.order_by(ActivityEvent._published_at.desc(), ActivityEvent._id.desc()).limit(
            limit
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def exists_for_match(self, match_id: str) -> bool:
        stmt = (
            select(activity_events_table.c.id)
            .where(activity_events_table.c.source_match_id == match_id)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def delete_for_user(
        self, user_id: UserId, types: Collection[ActivityEventType] | None = None
    ) -> int:
        stmt = delete(activity_events_table).where(activity_events_table.c.user_id == user_id)
        if types is not None:
            if not types:
                return 0
            stmt = stmt.where(activity_events_table.c.type.in_(sorted(types)))
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def delete_from_source(
        self,
        source_id: str,
        types: Collection[ActivityEventType],
        user_id: UserId | None = None,
    ) -> int:
        if not types:
            return 0
        stmt = delete(activity_events_table).where(
            activity_events_table.c.source_match_id == source_id,
            activity_events_table.c.type.in_(sorted(types)),
        )
        if user_id is not None:
            stmt = stmt.where(activity_events_table.c.user_id == user_id)
        return await self._borrar(stmt)

    async def delete_pairs(
        self, type: ActivityEventType, pairs: Sequence[tuple[UserId, str]]
    ) -> int:
        if not pairs:
            return 0
        tabla = activity_events_table.c
        stmt = delete(activity_events_table).where(
            tabla.type == type,
            tuple_(tabla.user_id, tabla.source_match_id).in_(list(pairs)),
        )
        return await self._borrar(stmt)

    async def lock_scope(self, scope_id: str) -> None:
        """
        `pg_advisory_xact_lock`: lo suelta el propio Postgres al acabar la
        transaccion, pase lo que pase. La clave lleva un prefijo para no
        chocar con otros candados por id.
        """
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:clave, 0))"),
            {"clave": f"activity-scope:{scope_id}"},
        )

    async def find_from_source(
        self, source_id: str, types: Collection[ActivityEventType]
    ) -> list[ActivityEvent]:
        if not types:
            return []
        stmt = select(ActivityEvent).where(
            activity_events_table.c.source_match_id == source_id,
            activity_events_table.c.type.in_(sorted(types)),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def last_published_at(
        self, competition_id: str, types: Collection[ActivityEventType]
    ) -> datetime | None:
        if not types:
            return None
        tabla = activity_events_table.c
        result = await self._session.execute(
            select(func.max(tabla.published_at)).where(
                tabla.payload["competition_id"].astext == competition_id,
                tabla.type.in_(sorted(types)),
            )
        )
        return result.scalar_one_or_none()

    async def find_for_users(
        self, user_ids: Collection[UserId], types: Collection[ActivityEventType]
    ) -> list[ActivityEvent]:
        if not user_ids or not types:
            return []
        stmt = select(ActivityEvent).where(
            activity_events_table.c.user_id.in_(list(user_ids)),
            activity_events_table.c.type.in_(sorted(types)),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_from_source_for_users(
        self,
        source_id: str,
        types: Collection[ActivityEventType],
        user_ids: Collection[UserId],
    ) -> int:
        if not types or not user_ids:
            return 0
        stmt = delete(activity_events_table).where(
            activity_events_table.c.source_match_id == source_id,
            activity_events_table.c.type.in_(sorted(types)),
            activity_events_table.c.user_id.in_(list(user_ids)),
        )
        return await self._borrar(stmt)

    async def delete_for_competition(
        self,
        competition_id: str,
        types: Collection[ActivityEventType],
        user_id: UserId | None = None,
    ) -> int:
        if not types:
            return 0
        stmt = delete(activity_events_table).where(
            activity_events_table.c.payload["competition_id"].astext == competition_id,
            activity_events_table.c.type.in_(sorted(types)),
        )
        if user_id is not None:
            stmt = stmt.where(activity_events_table.c.user_id == user_id)
        return await self._borrar(stmt)

    async def replace_for_competition(
        self,
        competition_id: str,
        types: Collection[ActivityEventType],
        events: list[ActivityEvent],
    ) -> None:
        tabla = activity_events_table.c
        if types:
            filas = (
                await self._session.execute(
                    select(
                        tabla.id,
                        tabla.user_id,
                        tabla.source_match_id,
                        tabla.type,
                        tabla.payload,
                        tabla.visible_to_friends,
                    ).where(
                        tabla.payload["competition_id"].astext == competition_id,
                        tabla.type.in_(sorted(types)),
                    )
                )
            ).all()
            nuevos = {(e.user_id, e.source_match_id, e.type): e for e in events}
            sobran = [
                fila.id
                for fila in filas
                if (nuevo := nuevos.get((fila.user_id, fila.source_match_id, fila.type))) is None
                or nuevo.payload != fila.payload
                # Lo oculto no se destapa: solo sobra lo visible que ahora se
                # publica oculto
                or (fila.visible_to_friends and not nuevo.visible_to_friends)
            ]
            if sobran:
                await self._borrar(delete(activity_events_table).where(tabla.id.in_(sobran)))
        await self.add_many(events)

    async def hide_from_friends(self, user_id: UserId, types: Collection[ActivityEventType]) -> int:
        if not types:
            return 0
        stmt = (
            update(activity_events_table)
            .where(
                activity_events_table.c.user_id == user_id,
                activity_events_table.c.type.in_(sorted(types)),
                activity_events_table.c.visible_to_friends.is_(True),
            )
            .values(visible_to_friends=False)
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def remember_withdrawn_tee_times(
        self, round_id: str, competition_id: str, user_ids: Collection[UserId]
    ) -> None:
        if not user_ids:
            return
        stmt = (
            pg_insert(withdrawn_tee_time_notices_table)
            .values(
                [
                    {"user_id": user_id, "round_id": round_id, "competition_id": competition_id}
                    for user_id in user_ids
                ]
            )
            .on_conflict_do_nothing(index_elements=["user_id", "round_id"])
        )
        await self._session.execute(stmt)

    async def withdrawn_tee_times(self, round_id: str) -> set[UserId]:
        stmt = select(withdrawn_tee_time_notices_table.c.user_id).where(
            withdrawn_tee_time_notices_table.c.round_id == round_id
        )
        result = await self._session.execute(stmt)
        return set(result.scalars().all())

    async def forget_withdrawn_tee_times(self, round_id: str, user_ids: Collection[UserId]) -> None:
        if not user_ids:
            return
        await self._session.execute(
            delete(withdrawn_tee_time_notices_table).where(
                withdrawn_tee_time_notices_table.c.round_id == round_id,
                withdrawn_tee_time_notices_table.c.user_id.in_(list(user_ids)),
            )
        )

    async def forget_withdrawn_tee_times_of_competition(
        self, competition_id: str, user_id: UserId | None = None
    ) -> None:
        stmt = delete(withdrawn_tee_time_notices_table).where(
            withdrawn_tee_time_notices_table.c.competition_id == competition_id
        )
        if user_id is not None:
            stmt = stmt.where(withdrawn_tee_time_notices_table.c.user_id == user_id)
        await self._session.execute(stmt)
