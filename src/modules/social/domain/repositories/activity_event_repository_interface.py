"""Interfaz del repositorio de eventos de actividad."""

from abc import ABC, abstractmethod
from datetime import datetime

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.user.domain.value_objects.user_id import UserId


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
    async def find_for_users(
        self, user_ids: list[UserId], limit: int, before: datetime | None = None
    ) -> list[ActivityEvent]:
        """
        Eventos de un conjunto de jugadores, del más reciente al más antiguo.

        `before` pagina por fecha y no por número de página: el feed crece por
        arriba, así que un desplazamiento numérico repetiría entradas cada vez
        que alguien publica algo mientras se navega.
        """

    @abstractmethod
    async def count_for_users_since(self, user_ids: list[UserId], since: datetime) -> int:
        """Cuántos eventos hay más nuevos que una fecha. Alimenta el aviso."""

    @abstractmethod
    async def exists_for_match(self, match_id: str) -> bool:
        """Si esa partida ya generó eventos, para no publicarlos dos veces."""

    @abstractmethod
    async def delete_for_user(self, user_id: UserId) -> int:
        """
        Borra todo lo publicado por un jugador.

        Hace falta al apagar la publicación de actividad: lo que ya se publicó
        debe desaparecer, no solo dejar de crecer.
        """
