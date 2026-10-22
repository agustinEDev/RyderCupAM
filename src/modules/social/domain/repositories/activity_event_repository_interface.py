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
    """

    @abstractmethod
    async def add_many(self, events: list[ActivityEvent]) -> None:
        """Publica varios eventos de una vez (los de una misma vuelta)."""

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
    async def delete_for_competition(
        self, competition_id: str, types: Collection[ActivityEventType]
    ) -> int:
        """
        Borra los eventos de esos tipos que cuentan algo de esa competicion
        (`payload.competition_id`), sea cual sea su origen. Para cuando la
        competicion se borra. Devuelve cuantos borro.
        """

    @abstractmethod
    async def hide_from_friends(self, user_id: UserId, types: Collection[ActivityEventType]) -> int:
        """
        Oculta a sus amigos lo publicado de esos tipos, sin borrarlo.

        Al apagar la publicacion, lo que tambien ve el autor (BOTH) se le queda
        a el: el interruptor decide lo que ven los demas, no lo que guarda uno
        de si mismo. Devuelve cuantos se ocultaron.
        """
