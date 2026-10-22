"""Puerto: que invitaciones ya no se pueden aceptar."""

from abc import ABC, abstractmethod
from collections.abc import Sequence


class InvitationAvailabilityInterface(ABC):
    """
    Lo que el feed necesita saber de las invitaciones de su pagina.

    Una invitacion puede caducar sola sin que nadie la toque: nadie la guarda
    como EXPIRED ni retira su «Te han invitado». Al leer, el feed y la
    actividad de un perfil preguntan aqui por los avisos de la pagina —el
    origen del aviso es el id de la invitacion— y ocultan los de las que ya no
    se pueden aceptar (revision final, 22 oct 2026).
    """

    @abstractmethod
    async def closed_ids(self, invitation_ids: Sequence[str]) -> set[str]:
        """
        De esos ids, los de invitaciones que ya no se pueden aceptar: no estan
        pendientes, caducaron, ya no existen o el id ni se puede leer. En una
        sola lectura.
        """
