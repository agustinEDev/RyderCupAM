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
from ..value_objects.estado_de_tarjeta import EstadoDeTarjeta
from ..value_objects.hoja_de_salidas import HojaDeSalidas
from ..value_objects.jugador_de_partida import JugadorDePartida
from ..value_objects.partida_id import PartidaId
from ..value_objects.round_id import RoundId
from .plazo_de_partidas import PartidaYaSalidaError


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
        salidas: Collection[PartidaId] = frozenset(),
    ) -> Cambios:
        """
        Args:
            partidas: Todas las de la franja
            jugador: Quien se mueve, con su foto (la de su partida, o una nueva si no tenía)
            destino_id: A qué partida; None para una nueva al final
            intercambiar_con: Con quién de la de destino se cambia, si se cambia
            salidas: Las que ya salieron (#544): ni origen ni destino; y con alguna
                fuera, nadie cambia de hora (la que se vacía deja su hueco)

        Raises:
            MovimientoImposibleError: Si no se puede, con el motivo
            PartidaYaSalidaError: Si el origen o el destino ya han salido
        """
        origen = next((p for p in partidas if jugador.user_id in p.user_ids), None)
        MovimientosDePartidas._no_presentado(origen, jugador.user_id)
        destino = MovimientosDePartidas._destino(partidas, destino_id, origen)
        if any(p is not None and p.id in salidas for p in (origen, destino)):
            raise PartidaYaSalidaError("Esa partida ya ha salido: no se puede cambiar.")
        if intercambiar_con is not None:
            return MovimientosDePartidas._intercambiar(
                origen, destino, jugador, intercambiar_con, hoja
            )
        se_vacia = origen is not None and len(origen.jugadores) == 1
        quedan = [p for p in partidas if not (se_vacia and p is origen)]
        # Con alguna fuera nadie cambia de hora: la nueva va detrás de la última
        con_huecos = bool(salidas)
        siguiente = (
            max((p.numero for p in quedan), default=0) + 1 if con_huecos else len(quedan) + 1
        )
        MovimientosDePartidas._comprobar(origen, destino, jugador, siguiente, hoja)

        cambios = Cambios()
        if origen is not None:
            if se_vacia:
                cambios.borrar.append(origen)
            else:
                origen.quitar(jugador.user_id)
                cambios.a_guardar(origen)
        # Sin huecos en la hoja: las de detrás de la que desaparece suben (M3),
        # salvo con la franja ya empezada, que deja el hueco (#544)
        for numero, partida in enumerate(sorted(quedan, key=lambda p: p.numero), start=1):
            if not con_huecos and partida.numero != numero:
                partida.renumerar(numero)
                cambios.a_guardar(partida)
        if destino is None:
            cambios.crear.append(Partida.crear(competition_id, round_id, siguiente, [jugador]))
        else:
            destino.meter(jugador, hoja.jugadores_por_partida)
            cambios.a_guardar(destino)
        return cambios

    @staticmethod
    def _no_presentado(partida: Partida | None, user_id: UserId) -> None:
        """Un no presentado se queda en su partida, que es donde sale su NP (12 oct 2026)."""
        if (
            partida is not None
            and partida.estados_de_tarjeta[user_id] == EstadoDeTarjeta.NO_PRESENTADO
        ):
            raise MovimientoImposibleError(
                "PLAYER_IS_NO_SHOW", "Es no presentado: se queda en su partida."
            )

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
        origen: Partida | None,
        destino: Partida | None,
        jugador: JugadorDePartida,
        siguiente: int,
        hoja: HojaDeSalidas,
    ) -> None:
        """
        Sin intercambio: hueco en el destino, el origen no se queda con uno, salidas
        libres. Los no presentados no ocupan sitio (2.ª pasada del QA, 12 oct 2026).
        """
        if destino is not None and len(destino.quedan) >= hoja.jugadores_por_partida:
            raise MovimientoImposibleError(
                "GROUP_FULL",
                "La partida está llena: intercambia al jugador con uno de ella.",
            )
        # Sin el que se va, uno solo jugando; solo con no presentados sí vale (12 oct 2026)
        siguen = [u for u in origen.quedan if u != jugador.user_id] if origen else []
        if len(siguen) == 1:
            raise MovimientoImposibleError(
                "ORIGIN_WOULD_BE_ALONE",
                "Su partida se quedaría con un solo jugador: intercámbialo, o mueve antes al otro.",
            )
        if destino is None and siguiente > hoja.numero_de_salidas:
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
        MovimientosDePartidas._no_presentado(destino, otro.user_id)
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
    def reordenar(
        partidas: Sequence[Partida],
        orden: Sequence[PartidaId],
        salidas: Collection[PartidaId] = frozenset(),
    ) -> list[Partida]:
        """
        Las partidas en el orden dado, con los números que ya hay (1, 2, 3… sin
        huecos; con huecos, los mismos). Las que ya salieron no cambian de sitio (#544).

        Raises:
            MovimientoImposibleError: Si el orden no tiene todas, una vez cada una
            PartidaYaSalidaError: Si mueve alguna que ya salió
        """
        if len(set(orden)) != len(orden) or set(orden) != {p.id for p in partidas}:
            raise MovimientoImposibleError(
                "INVALID_GROUP_ORDER", "El orden tiene que llevar todas las partidas, una vez."
            )
        por_id = {p.id: p for p in partidas}
        nuevos = dict(zip(orden, sorted(p.numero for p in partidas), strict=True))
        if any(por_id[pid].numero != nuevos[pid] for pid in salidas if pid in por_id):
            raise PartidaYaSalidaError("Esa partida ya ha salido: no cambia de hora.")
        for partida_id, numero in nuevos.items():
            if por_id[partida_id].numero != numero:
                por_id[partida_id].renumerar(numero)
        return list(partidas)
