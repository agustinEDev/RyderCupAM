"""
Domain Service: lo que se apunta de un logro al retirarlo, y como se aplica
cuando se vuelve a publicar (decisiones de Agustin del 23 oct 2026). Puro.

- El mismo logro (jugador, tipo y vuelta) conserva su fecha: no sube ni
  cuenta como nuevo.
- Lo que se retiro oculto vuelve oculto; en birdie, eagle y hoyo en uno solo
  si vuelve alguno de sus hoyos ocultos (sin hoyos apuntados, todos).
- «Campo nuevo» y «primer torneo» nacen ocultos si se retiro oculto otro del
  mismo jugador (y campo), venga de la vuelta que venga.

Los apuntes no se gastan: lo que estuvo oculto se queda oculto.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType


@dataclass(frozen=True)
class WithdrawnAchievement:
    """
    El apunte de un logro retirado. `published_at` es None en los de la
    2.38.0, que solo apuntaban lo oculto; `hidden_holes` None con `hidden`
    oculta todos los hoyos.
    """

    published_at: datetime | None
    hidden: bool
    hidden_holes: tuple[int, ...] | None = None
    golf_course_id: str | None = None

    @classmethod
    def of(
        cls,
        type: ActivityEventType,
        published_at: datetime,
        visible_to_friends: bool,
        payload: dict,
    ) -> "WithdrawnAchievement":
        """El apunte del logro que se retira."""
        oculto = not visible_to_friends
        campo = payload.get("golf_course_id") if type == ActivityEventType.NEW_COURSE else None
        return cls(
            published_at=published_at,
            hidden=oculto,
            hidden_holes=_holes(payload) if oculto and type.is_per_hole else None,
            golf_course_id=campo if isinstance(campo, str) else None,
        )

    def merged_with(self, nuevo: "WithdrawnAchievement") -> "WithdrawnAchievement":
        """
        Este apunte mas otro del mismo logro: la primera fecha y lo oculto de
        los dos. Los hoyos ocultos se juntan; si alguno los ocultaba todos,
        todos.
        """
        fechas = [f for f in (self.published_at, nuevo.published_at) if f is not None]
        if not self.hidden:
            hoyos = nuevo.hidden_holes
        elif not nuevo.hidden:
            hoyos = self.hidden_holes
        elif self.hidden_holes is None or nuevo.hidden_holes is None:
            hoyos = None
        else:
            hoyos = tuple(sorted(set(self.hidden_holes) | set(nuevo.hidden_holes)))
        return WithdrawnAchievement(
            published_at=min(fechas, default=None),
            hidden=self.hidden or nuevo.hidden,
            hidden_holes=hoyos,
            golf_course_id=nuevo.golf_course_id or self.golf_course_id,
        )

    def apply_to(self, event: ActivityEvent) -> None:
        """Lo apuntado, sobre el mismo logro que se vuelve a publicar."""
        if self.published_at is not None:
            event.keep_published_at(self.published_at)
        if self.hidden and self._would_reveal(event):
            event.hide_from_friends()

    def _would_reveal(self, event: ActivityEvent) -> bool:
        """Si publicarlo visible destaparia algo oculto."""
        # Sin hoyos apuntados, todos: un apunte vacio no destapa nada
        if not event.type.is_per_hole or not self.hidden_holes:
            return True
        hoyos = _holes(event.payload)
        return hoyos is None or bool(set(hoyos) & set(self.hidden_holes))


def _holes(payload: dict) -> tuple[int, ...] | None:
    """Los hoyos de un logro, o None si no dice ninguno valido."""
    hoyos = payload.get("holes")
    if not isinstance(hoyos, list):
        return None
    validos = tuple(sorted({h for h in hoyos if isinstance(h, int)}))
    return validos or None


def exclusive_scope(user_id, type: ActivityEventType, golf_course_id: str | None) -> tuple:
    """
    Entre que logros exclusivos se elige uno, y se hereda lo oculto: jugador,
    tipo y, en «campo nuevo», campo.
    """
    return user_id, type, golf_course_id if type == ActivityEventType.NEW_COURSE else None


def scope_of(event: ActivityEvent) -> tuple:
    """El ambito de un logro exclusivo que se publica."""
    campo = event.payload.get("golf_course_id")
    return exclusive_scope(event.user_id, event.type, campo if isinstance(campo, str) else None)


def cards_keep_their_date(events: list[ActivityEvent], published: dict[str, datetime]) -> None:
    """
    Todos los logros de una tarjeta (los de una vuelta de un jugador) con una
    sola fecha: el feed los agrupa y una tarjeta no se parte (hallazgo 2 del
    revisor, Agustin, 23 oct 2026).

    Si la tarjeta ya tiene logros publicados (`published`, la fecha mas
    antigua de cada una), lo que llega se pone con ellos: lo publicado no se
    mueve. Si no, la mas antigua de lo que llega, que puede ser la que
    conservo un logro al volver. Los avisos son cada uno su tarjeta.
    """
    fechas = dict(published)
    nuevas: dict[str, datetime] = {}
    for event in events:
        if event.type.is_achievement and event.card_key not in fechas:
            clave = event.card_key
            nuevas[clave] = min(nuevas.get(clave, event.published_at), event.published_at)
    fechas.update(nuevas)
    for event in events:
        if event.type.is_achievement:
            event.keep_published_at(fechas[event.card_key])
