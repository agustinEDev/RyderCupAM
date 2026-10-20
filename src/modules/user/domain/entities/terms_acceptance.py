"""
Terms Acceptance Entity - Domain Layer

Una fila del historial de aceptaciones de los Términos de uso.
"""

from datetime import datetime, timedelta

from ..services import terms_of_service
from ..value_objects.terms_acceptance_id import TermsAcceptanceId
from ..value_objects.user_id import UserId

# Largo de las columnas: la IPv6 más larga escrita cabe en 45; el navegador se
# acota a lo mismo que acepta la validación de User-Agent de la API
IP_ADDRESS_MAX_LENGTH = 45
USER_AGENT_MAX_LENGTH = 500


class TermsAcceptance:
    """
    Constancia de que un usuario aceptó una versión de los Términos.

    Es un historial de solo inserción (decisión de Agustín, 20 oct 2026): cada
    aceptación real añade una fila y ninguna se modifica. El estado actual
    (qué versión tiene aceptada) sigue en el usuario; aquí queda el rastro de
    cuándo, desde qué IP y con qué navegador aceptó cada versión.
    """

    def __init__(
        self,
        id: TermsAcceptanceId,
        user_id: UserId,
        terms_version: str,
        accepted_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ):
        self._id = id
        self._user_id = user_id
        self._terms_version = terms_version
        self._accepted_at = accepted_at
        self._ip_address = ip_address
        self._user_agent = user_agent

    @property
    def id(self) -> TermsAcceptanceId:
        return self._id

    @property
    def user_id(self) -> UserId:
        return self._user_id

    @property
    def terms_version(self) -> str:
        return self._terms_version

    @property
    def accepted_at(self) -> datetime:
        return self._accepted_at

    @property
    def ip_address(self) -> str | None:
        return self._ip_address

    @property
    def user_agent(self) -> str | None:
        return self._user_agent

    @classmethod
    def record(
        cls,
        user_id: UserId,
        terms_version: str,
        accepted_at: datetime,
        ip_address: str | None,
        user_agent: str | None,
    ) -> "TermsAcceptance":
        """
        Registra una aceptación.

        Args:
            user_id: Quién acepta
            terms_version: La versión aceptada
            accepted_at: Cuándo, con zona horaria (UTC)
            ip_address: IP del cliente, o None si no se conoce. Una más larga
                que la columna no se guarda: recortarla daría otra IP
            user_agent: Navegador, o None. Se recorta al largo de la columna

        Raises:
            ValueError: Si la versión no es válida o la fecha no lleva zona
        """
        if (
            not terms_version.strip()
            or len(terms_version) > terms_of_service.TERMS_VERSION_MAX_LENGTH
        ):
            raise ValueError(f"Versión de los Términos no válida: {terms_version!r}")
        # Sin zona, utcoffset() es None: también se rechaza
        if accepted_at.utcoffset() != timedelta(0):
            raise ValueError("accepted_at debe ir en UTC, con zona horaria")
        if ip_address is not None and len(ip_address) > IP_ADDRESS_MAX_LENGTH:
            ip_address = None
        if user_agent is not None:
            user_agent = user_agent[:USER_AGENT_MAX_LENGTH]
        return cls(
            id=TermsAcceptanceId.generate(),
            user_id=user_id,
            terms_version=terms_version,
            accepted_at=accepted_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def __repr__(self) -> str:
        return (
            f"TermsAcceptance(id={self.id}, user_id={self.user_id}, "
            f"terms_version={self.terms_version!r}, accepted_at={self.accepted_at})"
        )
