"""Interfaz del repositorio de eventos de actividad."""

from abc import ABC, abstractmethod
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.user.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class ActivitySlice:
    """
    Un trozo de lo que alguien puede ver: de estos jugadores, estos tipos.

    El feed son dos trozos —lo mio que veo yo y lo de mis amigos que ven ellos—
    y se piden en **una sola consulta**, no en dos que luego se mezclan: si no,
    la pagina y el cursor dejarian de cuadrar.

    `only_visible_to_friends` es para el trozo de los amigos: lo que se publico
    con la publicacion apagada es solo de su autor.
    """

    user_ids: tuple[UserId, ...]
    types: frozenset[ActivityEventType]
    only_visible_to_friends: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.user_ids or not self.types


class ActivityEventRepositoryInterface(ABC):
    """
    Acceso a los eventos publicados.

    El feed se resuelve **leyendo**, no escribiendo: al pedirlo se consultan los
    eventos de los amigos de quien pregunta. No se crea una copia por amigo al
    publicar. Con el tamaño de esta aplicación es la opción correcta y con
    diferencia la más simple — el reparto en escritura solo compensa con miles
    de seguidores por cuenta, y a cambio trae duplicación y reconciliación cada
    vez que alguien acepta o deshace una amistad.

    **Lo que se vuelve a publicar** (decisiones del 23 oct 2026). Todo
    borrado de un logro lo apunta, y el apunte no se gasta nunca:

    - El mismo logro (jugador, tipo y origen) que se vuelve a publicar
      conserva su fecha: no sube ni cuenta como nuevo.
    - Si se retiro oculto, vuelve oculto aunque llegue visible; en birdie,
      eagle y hoyo en uno, solo si vuelve alguno de sus hoyos ocultos.
    - «Campo nuevo» y «primer torneo» nacen ocultos si se retiro oculto otro
      del mismo jugador (y campo): la herencia no destapa.

    Asi reabrir y volver a cerrar un torneo, o heredar, no destapa lo que se
    publico con la publicacion apagada. Lo visible que llega oculto entra
    oculto: apagarla oculta lo publicado. Solo los logros: los avisos que se
    repiten (apuntarse otra vez) son nuevos y toman el interruptor de ahora.
    `delete_for_user` no apunta: es el interruptor y la cuenta, no una
    retirada para volver a publicar.
    """

    @abstractmethod
    async def add_many(self, events: list[ActivityEvent]) -> None:
        """
        Publica varios eventos de una vez (los de una misma vuelta). Lo que ya
        estaba no se toca, y un logro que se retiro vuelve con lo apuntado.
        """

    @abstractmethod
    async def find_in(
        self,
        slices: Sequence[ActivitySlice],
        limit: int,
        before: datetime | None = None,
        before_id: UUID | None = None,
    ) -> list[ActivityEvent]:
        """
        Los eventos de varios trozos en una sola pagina, del más reciente al más
        antiguo por fecha de publicación.

        Se pagina por cursor y no por número de página: el feed crece por
        arriba, así que un desplazamiento numérico repetiría entradas cada vez
        que alguien publica algo mientras se navega.

        El cursor son **las dos cosas**, `before` y `before_id`, porque la fecha
        sola no es única: todos los eventos de una misma publicación comparten
        `published_at`. Paginar solo por fecha se dejaría fuera los que aún no se
        han enseñado.
        """

    @abstractmethod
    async def count_in(
        self,
        slices: Sequence[ActivitySlice],
        since: datetime | None,
        cap: int | None = None,
        skip_private_enrollments: bool = False,
        open_invitations_at: datetime | None = None,
        hide_trashed_quick_matches_from: UserId | None = None,
    ) -> int:
        """
        Cuantas tarjetas de esos trozos se publicaron despues de `since` (todas
        si es None), sin pasar de `cap`. Alimenta el aviso de novedades.

        Cuenta tarjetas y no filas (`ActivityEvent.card_key`): tres logros de
        una vuelta se ven como una tarjeta, y el numero tiene que decir lo que
        hay en la pantalla.

        Con `skip_private_enrollments` no cuenta los ENROLLED_IN_TOURNAMENT de
        torneos que ahora son privados: el feed no los enseña (regla E, 22 oct
        2026), y el numero tiene que decir lo mismo que la pantalla.

        Con `open_invitations_at` tampoco cuenta los INVITED_TO_TOURNAMENT de
        invitaciones que en ese instante ya no se pueden aceptar (no pendientes,
        caducadas o borradas), que el feed tampoco enseña.

        Con `hide_trashed_quick_matches_from` (quien mira) tampoco cuenta lo
        que salio de una partida rapida que su autor tiene en la papelera
        (`ActivityEvent.comes_from_a_quick_match`), salvo lo de quien mira.
        """

    @abstractmethod
    async def exists_for_match(self, match_id: str) -> bool:
        """Si esa partida ya generó eventos, para no publicarlos dos veces."""

    @abstractmethod
    async def delete_for_user(
        self, user_id: UserId, types: Collection[ActivityEventType] | None = None
    ) -> int:
        """
        Borra lo publicado por un jugador: todo, o solo esos tipos.

        Hace falta al apagar la publicacion de actividad: lo que solo era para
        sus amigos debe desaparecer, no solo dejar de crecer.
        """

    @abstractmethod
    async def delete_from_source(
        self,
        source_id: str,
        types: Collection[ActivityEventType],
        user_id: UserId | None = None,
    ) -> int:
        """
        Borra lo publicado desde ese origen (`source_match_id`) de esos tipos:
        de un jugador, o de todos si no se dice. Devuelve cuantos borro.

        Es como se retira un aviso que deja de ser cierto: la invitacion
        retirada, el amigo que se borra del torneo, la clasificacion de un
        torneo que se reabre. Una lista de tipos vacia no borra nada.
        """

    @abstractmethod
    async def delete_pairs(
        self, type: ActivityEventType, pairs: Sequence[tuple[UserId, str]]
    ) -> int:
        """
        Borra los eventos de ese tipo de cada pareja (jugador, origen), todos en
        una sola operacion. Para retirar en lote los avisos de las invitaciones
        que se cierran solas. Sin parejas no borra nada. Devuelve cuantos borro.
        """

    @abstractmethod
    async def lock_scope(self, scope_id: str) -> None:
        """
        Bloquea ese ambito (un torneo) hasta el final de la transaccion: dos
        publicaciones de salidas del torneo, o una publicacion y la baja o la
        cancelacion que borran sus avisos, no se cruzan, y la segunda ve lo
        que dejo la primera (G3, revision del 22 oct 2026).
        """

    @abstractmethod
    async def find_from_source(
        self, source_id: str, types: Collection[ActivityEventType]
    ) -> list[ActivityEvent]:
        """Lo publicado desde ese origen de esos tipos, de todos los jugadores."""

    @abstractmethod
    async def last_written_at(
        self, competition_id: str, types: Collection[ActivityEventType]
    ) -> datetime | None:
        """
        Cuando se escribio lo ultimo de esos tipos para esa competicion
        (`payload.competition_id`), o None si no hay nada. Dice si otra
        publicacion del torneo escribio mientras se calculaba la propia. No es
        la fecha de publicacion: el mismo logro que se vuelve a publicar
        conserva la suya (23 oct 2026).
        """

    @abstractmethod
    async def authors_in_competition(
        self, slice_: ActivitySlice, competition_id: str
    ) -> set[UserId]:
        """
        Los autores de ese trozo con algun evento de esa competicion
        (`payload.competition_id`). La llave de una privada (tabla del 27 oct
        2026): quien esta fuera ve lo jugado de esos amigos.
        """

    @abstractmethod
    async def find_for_users(
        self, user_ids: Collection[UserId], types: Collection[ActivityEventType]
    ) -> list[ActivityEvent]:
        """
        Lo publicado por esos jugadores de esos tipos, sea cual sea su origen:
        con esto se comparan los logros exclusivos por fecha (22 oct 2026).
        Sin jugadores o sin tipos no devuelve nada.
        """

    @abstractmethod
    async def delete_from_source_for_users(
        self,
        source_id: str,
        types: Collection[ActivityEventType],
        user_ids: Collection[UserId],
    ) -> int:
        """
        Como `delete_from_source`, pero de varios jugadores de una vez: las
        salidas de una ronda se sustituyen por lotes (G3), y uno por jugador
        serian tantas consultas como jugadores. Sin jugadores no borra nada.
        """

    @abstractmethod
    async def remember_withdrawn_tee_times(
        self, round_id: str, competition_id: str, user_ids: Collection[UserId]
    ) -> None:
        """
        Apunta que esos jugadores perdieron su aviso de salida de esa ronda por
        un cambio en ella —se quedaron sin partido o sin grupo—, no por una
        baja ni una cancelacion. Si luego vuelven a tener salida en la ronda,
        su aviso nuevo es un cambio (`changed`), no el primero (prueba de punta
        a punta del 22 oct 2026: reasignar en dos pasos). Repetirlo no duplica.
        """

    @abstractmethod
    async def withdrawn_tee_times(self, round_id: str) -> set[UserId]:
        """Quien perdio su aviso de salida de esa ronda por un cambio y aun no lo recupero."""

    @abstractmethod
    async def forget_withdrawn_tee_times(self, round_id: str, user_ids: Collection[UserId]) -> None:
        """Olvida esos apuntes de la ronda: esos jugadores ya tienen salida otra vez."""

    @abstractmethod
    async def forget_withdrawn_tee_times_of_competition(
        self, competition_id: str, user_id: UserId | None = None
    ) -> None:
        """
        Olvida los apuntes de ese torneo, de un jugador o de todos: tras una
        baja o una cancelacion, la siguiente salida es nueva de verdad.
        """

    @abstractmethod
    async def delete_for_competition(
        self,
        competition_id: str,
        types: Collection[ActivityEventType],
        user_id: UserId | None = None,
    ) -> int:
        """
        Borra los eventos de esos tipos que cuentan algo de esa competicion
        (`payload.competition_id`), sea cual sea su origen: de un jugador, o de
        todos si no se dice. Para cuando la competicion se borra o se cancela,
        o un jugador se retira de ella. Devuelve cuantos borro.
        """

    @abstractmethod
    async def replace_for_competition(
        self,
        competition_id: str,
        types: Collection[ActivityEventType],
        events: list[ActivityEvent],
    ) -> None:
        """
        Deja de esos tipos, para esa competicion (`payload.competition_id`),
        exactamente `events`: borra lo que ya no esta o ha cambiado (otro
        `payload`, o visible y ahora oculto) y publica lo que falta. Lo que ya
        estaba igual no se toca: conserva su id y su fecha de publicacion, asi
        que repetir la misma publicacion no lo vuelve a dar por nuevo. Lo que
        estaba oculto sigue oculto aunque ahora llegue visible.

        Es como se publica el ultimo cierre de un torneo sobre lo del anterior
        (revision final del 22 oct 2026). Quien llama toma antes el candado
        del torneo.
        """

    @abstractmethod
    async def hide_from_friends(self, user_id: UserId, types: Collection[ActivityEventType]) -> int:
        """
        Oculta a sus amigos lo publicado de esos tipos, sin borrarlo.

        Al apagar la publicacion, lo que tambien ve el autor (BOTH) se le queda
        a el: el interruptor decide lo que ven los demas, no lo que guarda uno
        de si mismo. Devuelve cuantos se ocultaron.
        """
