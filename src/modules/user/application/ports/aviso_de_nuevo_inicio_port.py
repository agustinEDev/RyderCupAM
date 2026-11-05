"""El puerto del aviso de «nuevo inicio de sesión» (BE #737)."""

from typing import Protocol

from src.modules.user.domain.value_objects.user_id import UserId


class IAvisoDeNuevoInicio(Protocol):
    """Quien avisa al usuario de que se ha entrado desde un dispositivo nuevo.

    El login no espera al correo: la implementación de la API lo manda en segundo
    plano. Nunca lanza.
    """

    async def avisa(
        self,
        user_id: UserId,
        email: str,
        nombre: str,
        device_id: str | None,
        es_nuevo: bool,
        verificado: bool,
        es_alta: bool = False,
    ) -> None:
        """Avisa, si toca, del inicio de sesión desde `device_id`."""
        ...
