"""
MovimientosDePartidas - Mover jugadores entre partidas y reordenarlas (#251, PR 4).

Decidido con Agustín el 9 oct 2026:

- A una partida llena se entra **intercambiando** con uno de ella (D13).
- También a una **partida nueva al final**, si quedan salidas: nace de 1,
  incompleta, y se completa moviendo a otro (M1, excepción a D4).
- Al mover, el origen **nunca se queda con uno solo**, salvo intercambio (M2).
- Si una partida se **vacía**, desaparece y las de detrás suben: sus horas se
  adelantan un intervalo, sin huecos en la hoja (M3).

Aquí solo están las reglas; el plazo y quién puede, los mira quien llama.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field

from src.modules.user.domain.value_objects.user_id import UserId

from ..entities.partida import Partida
from ..value_objects.competition_id import CompetitionId
from ..value_objects.hoja_de_salidas import HojaDeSalidas
from ..value_objects.jugador_de_partida import JugadorDePartida
from ..value_objects.partida_id import PartidaId
from ..value_objects.round_id import RoundId
from .marcadores_en_cadena import MIN_PARA_MARCAR


class MovimientoImposibleError(ValueError):
    """Ese movimiento no se puede hacer: `codigo` dice por qué, en una clave para la pantalla."""

    def __init__(self, codigo: str, mensaje: str):
        self.codigo = codigo
        super().__init__(mensaje)


@dataclass
class Cambios:
    """Lo que hay que guardar, crear y borrar tras un movimiento."""

    guardar: list[Partida] = field(default_factory=list)
    crear: list[Partida] = field(default_factory=list)
    borrar: list[Partida] = field(default_factory=list)

    def a_guardar(self, partida: Partida) -> None:
        if partida not in self.guardar:
            self.guardar.append(partida)


class MovimientosDePartidas:
    """Las reglas para mover jugadores y reordenar las partidas de una franja."""

    @staticmethod
    def mover(
        partidas: Sequence[Partida],
        jugador: JugadorDePartida,
        destino_id: PartidaId | None,
        intercambiar_con: UserId | None,
        hoja: HojaDeSalidas,
        competition_id: CompetitionId,
        round_id: RoundId,
    ) -> Cambios:
        """
        Args:
            partidas: Todas las de la franja
            jugador: Quien se mueve, con su foto (la de su partida, o una nueva si no tenía)
            destino_id: A qué partida; None para una nueva al final
            intercambiar_con: Con quién de la de destino se cambia, si se cambia

        Raises:
            MovimientoImposibleError: Si no se puede, con el motivo
        """
        origen = next((p for p in partidas if jugador.user_id in p.user_ids), None)
        destino = MovimientosDePartidas._destino(partidas, destino_id, origen)
        if intercambiar_con is not None:
            return MovimientosDePartidas._intercambiar(
                origen, destino, jugador, intercambiar_con, hoja
            )
        se_vacia = origen is not None and len(origen.jugadores) == 1
        quedan = [p for p in partidas if not (se_vacia and p is origen)]
        MovimientosDePartidas._comprobar(origen, destino, len(quedan), hoja)

        cambios = Cambios()
        if origen is not None:
            if se_vacia:
                cambios.borrar.append(origen)
            else:
                origen.quitar(jugador.user_id)
                cambios.a_guardar(origen)
        # Sin huecos en la hoja: las de detrás de la que desaparece suben (M3)
        for numero, partida in enumerate(sorted(quedan, key=lambda p: p.numero), start=1):
            if partida.numero != numero:
                partida.renumerar(numero)
                cambios.a_guardar(partida)
        if destino is None:
            cambios.crear.append(
                Partida.crear(competition_id, round_id, len(quedan) + 1, [jugador])
            )
        else:
            destino.meter(jugador, hoja.jugadores_por_partida)
            cambios.a_guardar(destino)
        return cambios

    @staticmethod
    def _destino(
        partidas: Sequence[Partida], destino_id: PartidaId | None, origen: Partida | None
    ) -> Partida | None:
        """La partida de destino, si es de la franja y no es la suya; None, una nueva."""
        if destino_id is None:
            return None
        destino = next((p for p in partidas if p.id == destino_id), None)
        if destino is None:
            raise MovimientoImposibleError(
                "GROUP_NOT_IN_WINDOW", "Esa partida no es de esta franja."
            )
        if destino is origen:
            raise MovimientoImposibleError("ALREADY_IN_GROUP", "Ya está en esa partida.")
        return destino

    @staticmethod
    def _comprobar(
        origen: Partida | None, destino: Partida | None, quedan: int, hoja: HojaDeSalidas
    ) -> None:
        """Sin intercambio: hueco en el destino, el origen no se queda con uno, salidas libres."""
        if destino is not None and len(destino.jugadores) >= hoja.jugadores_por_partida:
            raise MovimientoImposibleError(
                "GROUP_FULL",
                "La partida está llena: intercambia al jugador con uno de ella.",
            )
        if origen is not None and len(origen.jugadores) == MIN_PARA_MARCAR:
            raise MovimientoImposibleError(
                "ORIGIN_WOULD_BE_ALONE",
                "Su partida se quedaría con un solo jugador: intercámbialo, o mueve antes al otro.",
            )
        if destino is None and quedan >= hoja.numero_de_salidas:
            raise MovimientoImposibleError(
                "NO_FREE_TEE_TIME", "No quedan salidas libres para otra partida."
            )

    @staticmethod
    def _intercambiar(
        origen: Partida | None,
        destino: Partida | None,
        jugador: JugadorDePartida,
        intercambiar_con: UserId,
        hoja: HojaDeSalidas,
    ) -> Cambios:
        """Cada uno al sitio del otro; sin partida de origen, el otro se queda sin partida."""
        if destino is None:
            raise MovimientoImposibleError(
                "SWAP_NEEDS_GROUP", "Solo se intercambia con alguien de otra partida."
            )
        otro = next((j for j in destino.jugadores if j.user_id == intercambiar_con), None)
        if otro is None:
            raise MovimientoImposibleError(
                "SWAP_PLAYER_NOT_IN_GROUP", "Ese jugador no está en la partida de destino."
            )
        cambios = Cambios()
        destino.quitar(otro.user_id)
        destino.meter(jugador, hoja.jugadores_por_partida)
        if origen is not None:
            origen.quitar(jugador.user_id)
            origen.meter(otro, hoja.jugadores_por_partida)
            cambios.a_guardar(origen)
        cambios.a_guardar(destino)
        return cambios

    @staticmethod
    def sacar(
        partidas: Sequence[Partida],
        user_id: UserId,
        salidas: Collection[PartidaId] = frozenset(),
    ) -> Cambios:
        """
        Una baja (retirada, cambio de franja): sale de su partida si aún no ha salido.

        Aquí sí puede quedar una partida de 1, incompleta (D4); si se vacía,
        desaparece y las de detrás suben (M3). Si ya salió, lo jugado se queda.

        Args:
            salidas: Las que ya salieron aunque su estado no lo diga: les llegó la
                hora (hasta la PR 5 nadie las pasa a IN_PROGRESS)
        """

        def salio(partida: Partida) -> bool:
            return partida.empezada or partida.id in salidas

        cambios = Cambios()
        origen = next((p for p in partidas if user_id in p.user_ids), None)
        if origen is None or salio(origen):
            return cambios
        if len(origen.jugadores) > 1:
            origen.quitar(user_id)
            cambios.a_guardar(origen)
            return cambios
        cambios.borrar.append(origen)
        quedan = [p for p in partidas if p is not origen]
        # Ya en juego, nadie cambia de hora: la que se vacía deja su hueco
        if any(salio(p) for p in quedan):
            return cambios
        for numero, partida in enumerate(sorted(quedan, key=lambda p: p.numero), start=1):
            if partida.numero != numero:
                partida.renumerar(numero)
                cambios.a_guardar(partida)
        return cambios

    @staticmethod
    def reordenar(partidas: Sequence[Partida], orden: Sequence[PartidaId]) -> list[Partida]:
        """
        Las partidas en el orden dado, numeradas desde 1.

        Raises:
            MovimientoImposibleError: Si el orden no tiene todas, una vez cada una
        """
        if len(set(orden)) != len(orden) or set(orden) != {p.id for p in partidas}:
            raise MovimientoImposibleError(
                "INVALID_GROUP_ORDER", "El orden tiene que llevar todas las partidas, una vez."
            )
        por_id = {p.id: p for p in partidas}
        for numero, partida_id in enumerate(orden, start=1):
            por_id[partida_id].renumerar(numero)
        return list(partidas)
