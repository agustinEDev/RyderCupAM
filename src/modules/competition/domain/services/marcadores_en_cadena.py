"""
MarcadoresEnCadena - Quién marca a quién en una partida de stroke play (#251).

Decidido con Agustín el 6 oct 2026 (marcadores en cadena) y el 9 oct (D12):

- Por defecto, **en cadena**: cada jugador marca al siguiente y el último al
  primero; en una de 2, se marcan el uno al otro.
- El organizador puede cambiarla, pero **nadie se marca a sí mismo** y cada
  jugador marca a uno y es marcado por uno: una biyección sin puntos fijos.
- Una partida de 1 (solo por bajas, D4) se queda sin marcador.
"""

from collections.abc import Mapping, Sequence

from src.modules.user.domain.value_objects.user_id import UserId

# Hace falta otro jugador al que marcar: una partida de 1 no tiene marcador (D4)
MIN_PARA_MARCAR = 2


class MarcadoresInvalidosError(ValueError):
    """La asignación de marcadores no es posible en esa partida."""


class MarcadoresEnCadena:
    """Las reglas de los marcadores de una partida."""

    @staticmethod
    def de(jugadores: Sequence[UserId]) -> dict[UserId, UserId]:
        """La cadena por defecto, en el orden de la partida: marcador -> marcado."""
        if len(jugadores) < MIN_PARA_MARCAR:
            return {}
        return {
            jugador: jugadores[(posicion + 1) % len(jugadores)]
            for posicion, jugador in enumerate(jugadores)
        }

    @staticmethod
    def validar(jugadores: Sequence[UserId], marcadores: Mapping[UserId, UserId]) -> None:
        """
        Args:
            jugadores: Los de la partida
            marcadores: marcador -> marcado

        Raises:
            MarcadoresInvalidosError: Si no es una biyección sin puntos fijos
                sobre los jugadores de la partida
        """
        en_la_partida = set(jugadores)
        if len(en_la_partida) < MIN_PARA_MARCAR:
            if marcadores:
                raise MarcadoresInvalidosError("Una partida de un jugador no tiene marcador.")
            return
        if set(marcadores) != en_la_partida:
            raise MarcadoresInvalidosError("Cada jugador de la partida marca a uno, y solo ellos.")
        if set(marcadores.values()) != en_la_partida:
            raise MarcadoresInvalidosError("Cada jugador de la partida tiene un solo marcador.")
        if any(marcador == marcado for marcador, marcado in marcadores.items()):
            raise MarcadoresInvalidosError("Nadie se marca a sí mismo.")
