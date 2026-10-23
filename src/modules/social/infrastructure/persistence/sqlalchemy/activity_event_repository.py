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
    literal_column,
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
from src.modules.social.domain.services.withdrawn_achievement import (
    WithdrawnAchievement,
    cards_keep_their_date,
    exclusive_scope,
    scope_of,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.persistence.mappers.activity_event_mapper import (
    activity_events_table,
    withdrawn_hidden_achievements_table,
    withdrawn_tee_time_notices_table,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.utc_clock import utc_now

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

        Un logro que se retiro vuelve con su fecha y, si estaba oculto,
        oculto (`_aplicar_apuntes`).
        """
        if not events:
            return
        await self._aplicar_apuntes(events)
        cards_keep_their_date(events, await self._fechas_de_tarjeta(events))

        # Con el reloj de la aplicacion, como el `calculado_en` con el que se
        # compara al publicar un torneo
        escrito = utc_now()
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
                "written_at": escrito,
            }
            for event in events
        ]

        stmt = pg_insert(activity_events_table).values(filas)
        await self._session.execute(
            stmt.on_conflict_do_nothing(constraint=UQ_ACTIVITY_EVENTS_MATCH_TYPE)
        )

    async def _aplicar_apuntes(self, events: list[ActivityEvent]) -> None:
        """
        Aplica a los logros que llegan lo apuntado al retirar otros (decisiones
        del 23 oct 2026). Los apuntes no se gastan: lo que estuvo oculto se
        queda oculto aunque se publique muchas veces.

        - El mismo logro (jugador, tipo y origen) conserva su fecha.
        - Y si se retiro oculto, vuelve oculto; en birdie, eagle y hoyo en uno
          solo si vuelve alguno de sus hoyos ocultos (un apunte sin hoyos los
          oculta todos).
        - «Campo nuevo» y «primer torneo» nacen ocultos si se retiro oculto
          otro del mismo jugador (y campo), venga de la vuelta que venga.

        Si el alta se salta por la clave unica, el logro que ya estaba se queda
        como estaba.
        """
        logros = [e for e in events if e.type.is_achievement]
        if not logros:
            return
        apuntes = withdrawn_hidden_achievements_table.c
        filas = (
            await self._session.execute(
                select(withdrawn_hidden_achievements_table).where(
                    apuntes.user_id.in_(list({e.user_id for e in logros})),
                    apuntes.type.in_(sorted({e.type for e in logros})),
                    # Los apuntes no se borran nunca: solo los de estas vueltas,
                    # salvo los exclusivos, que se heredan de cualquier vuelta
                    or_(
                        apuntes.source_match_id.in_(sorted({e.source_match_id for e in logros})),
                        apuntes.type.in_(
                            sorted(t for t in ActivityEventType if t.is_exclusive_by_date)
                        ),
                    ),
                )
            )
        ).all()
        por_clave = {(f.user_id, f.type, f.source_match_id): _de_la_fila(f) for f in filas}
        ocultos_exclusivos = {
            exclusive_scope(f.user_id, f.type, f.golf_course_id)
            for f in filas
            if f.hidden and f.type.is_exclusive_by_date
        }

        for event in logros:
            apunte = por_clave.get((event.user_id, event.type, event.source_match_id))
            if apunte is not None:
                apunte.apply_to(event)
            if event.type.is_exclusive_by_date and scope_of(event) in ocultos_exclusivos:
                event.hide_from_friends()

    async def _fechas_de_tarjeta(self, events: list[ActivityEvent]) -> dict[str, datetime]:
        """La fecha mas antigua de cada tarjeta que ya tiene logros publicados."""
        logros = [e for e in events if e.type.is_achievement]
        if not logros:
            return {}
        tabla = activity_events_table.c
        filas = (
            await self._session.execute(
                select(tabla.user_id, tabla.source_match_id, func.min(tabla.published_at))
                .where(
                    tabla.user_id.in_(list({e.user_id for e in logros})),
                    tabla.source_match_id.in_(sorted({e.source_match_id for e in logros})),
                    tabla.type.in_(sorted(t for t in ActivityEventType if t.is_achievement)),
                )
                .group_by(tabla.user_id, tabla.source_match_id)
            )
        ).all()
        return {f"{user_id.value}:{origen}": fecha for user_id, origen, fecha in filas}

    async def _borrar(self, stmt: Delete) -> int:
        """
        Borra y apunta los logros que se van: su fecha, si estaban ocultos (y
        en que hoyos) y el campo de un «campo nuevo». Los avisos no se apuntan:
        apuntarse otra vez a un torneo es un aviso nuevo.

        Si ya habia apunte de ese logro, se conserva la primera fecha y lo
        oculto se suma: nada que estuvo oculto deja de estarlo.
        """
        tabla = activity_events_table.c
        filas = (
            await self._session.execute(
                stmt.returning(
                    tabla.user_id,
                    tabla.type,
                    tabla.source_match_id,
                    tabla.visible_to_friends,
                    tabla.published_at,
                    tabla.payload,
                )
            )
        ).all()
        apuntes = [_a_la_fila(f) for f in filas if f.type.is_achievement]
        if apuntes:
            nuevo = pg_insert(withdrawn_hidden_achievements_table).values(apuntes)
            await self._session.execute(
                nuevo.on_conflict_do_update(
                    index_elements=["user_id", "source_match_id", "type"],
                    set_=_sumar_apuntes(nuevo.excluded),
                )
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

    async def last_written_at(
        self, competition_id: str, types: Collection[ActivityEventType]
    ) -> datetime | None:
        if not types:
            return None
        tabla = activity_events_table.c
        result = await self._session.execute(
            select(func.max(tabla.written_at)).where(
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


def _de_la_fila(fila) -> WithdrawnAchievement:
    hoyos = fila.hidden_holes
    return WithdrawnAchievement(
        published_at=fila.published_at,
        hidden=fila.hidden,
        hidden_holes=tuple(hoyos) if isinstance(hoyos, list) else None,
        golf_course_id=fila.golf_course_id,
    )


def _a_la_fila(fila) -> dict:
    """El apunte de un logro que se retira, a partir de lo que devolvio el borrado."""
    apunte = WithdrawnAchievement.of(
        fila.type, fila.published_at, fila.visible_to_friends, fila.payload
    )
    return {
        "user_id": fila.user_id,
        "source_match_id": fila.source_match_id,
        "type": fila.type,
        "published_at": apunte.published_at,
        "hidden": apunte.hidden,
        "hidden_holes": list(apunte.hidden_holes) if apunte.hidden_holes is not None else None,
        "golf_course_id": apunte.golf_course_id,
    }


def _sumar_apuntes(nuevo) -> dict:
    """
    `WithdrawnAchievement.merged_with` en SQL, para que dos retiradas a la vez
    no se pisen: la primera fecha (LEAST ignora el NULL de un apunte de la
    2.38.0) y lo oculto de los dos. Los hoyos ocultos se juntan; si alguno los
    ocultaba todos (NULL), todos.
    """
    viejo = withdrawn_hidden_achievements_table.c
    # Los dos ocultos: su union, sin repetir y en orden. Si alguno los ocultaba
    # todos (NULL), NULL: en Postgres `NULL || x` es NULL
    juntos = literal_column(
        "(SELECT jsonb_agg(DISTINCT h ORDER BY h) FROM jsonb_array_elements("
        "withdrawn_hidden_achievements.hidden_holes || excluded.hidden_holes) AS t(h))",
        JSONB,
    )
    return {
        "published_at": func.least(viejo.published_at, nuevo.published_at),
        "hidden": or_(viejo.hidden, nuevo.hidden),
        "hidden_holes": case(
            (not_(viejo.hidden), nuevo.hidden_holes),
            (not_(nuevo.hidden), viejo.hidden_holes),
            else_=juntos,
        ),
        "golf_course_id": func.coalesce(nuevo.golf_course_id, viejo.golf_course_id),
        "withdrawn_at": nuevo.withdrawn_at,
    }
