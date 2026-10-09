"""
Partida - Un grupo de stroke play que sale junto a su hora (#251, PR 4).

Decidido con Agustín el 6-9 oct 2026:

- Se genera por franja, de 3 o 4 jugadores; de 1 solo queda por bajas (D4):
  incompleta y sin marcador, hasta que el organizador la arregle.
- La hora no se guarda: sale de la hoja de salidas por su número, así que
  reordenar o mover la primera salida no deja horas viejas por ahí.
- Marcadores en cadena, que el organizador puede cambiar sin que nadie se marque
  a sí mismo (D12). Al meter o quitar a alguien, la cadena se rehace.
- Empezada, no se toca: ni jugadores, ni marcadores, ni número (D1, D2, D11).
"""

from collections.abc import Collection, Mapping, Sequence

from src.modules.user.domain.value_objects.user_id import UserId

from ..services.marcadores_en_cadena import MIN_PARA_MARCAR, MarcadoresEnCadena
from ..value_objects.competition_id import CompetitionId
from ..value_objects.estado_de_tarjeta import EstadoDeTarjeta
from ..value_objects.estado_partida import EstadoPartida
from ..value_objects.jugador_de_partida import JugadorDePartida
from ..value_objects.partida_id import PartidaId
from ..value_objects.round_id import RoundId

MAX_JUGADORES = 4


class PartidaInvalidaError(ValueError):
    """La partida no es posible, y el mensaje dice por qué."""


class PartidaEmpezadaError(ValueError):
    """La partida ya salió: no se toca."""


class PartidaNoEmpezadaError(ValueError):
    """La partida aún no ha empezado: no hay tarjeta que entregar."""


class TarjetaCerradaError(ValueError):
    """Esa tarjeta ya está entregada, retirada o sin presentarse."""


class Partida:
    """Un grupo que sale junto en una franja."""

    def __init__(
        self,
        id: PartidaId,
        competition_id: CompetitionId,
        round_id: RoundId,
        numero: int,
        jugadores: Sequence[JugadorDePartida],
        marcadores: Mapping[UserId, UserId],
        estado: EstadoPartida,
        estados_de_tarjeta: Mapping[UserId, EstadoDeTarjeta] | None = None,
    ):
        self._comprobar_numero(numero)
        self._comprobar_jugadores(jugadores)
        MarcadoresEnCadena.validar([j.user_id for j in jugadores], marcadores)
        self._id = id
        self._competition_id = competition_id
        self._round_id = round_id
        self._numero = numero
        self._jugadores = list(jugadores)
        self._marcadores = dict(marcadores)
        self._estado = estado
        self._tarjetas = {
            j.user_id: (estados_de_tarjeta or {}).get(j.user_id, EstadoDeTarjeta.JUGANDO)
            for j in jugadores
        }

    @classmethod
    def crear(
        cls,
        competition_id: CompetitionId,
        round_id: RoundId,
        numero: int,
        jugadores: Sequence[JugadorDePartida],
    ) -> "Partida":
        """Una partida nueva, sin salir, con los marcadores en cadena."""
        return cls(
            id=PartidaId.generate(),
            competition_id=competition_id,
            round_id=round_id,
            numero=numero,
            jugadores=jugadores,
            marcadores=MarcadoresEnCadena.de([j.user_id for j in jugadores]),
            estado=EstadoPartida.SCHEDULED,
        )

    # ==================== Comandos ====================

    def quitar(self, user_id: UserId) -> None:
        """Saca a un jugador; la cadena de marcadores se rehace con los que quedan."""
        self._sin_empezar()
        if user_id not in self.user_ids:
            raise PartidaInvalidaError("Ese jugador no está en la partida.")
        self._jugadores = [j for j in self._jugadores if j.user_id != user_id]
        self._tarjetas.pop(user_id, None)
        self._marcadores = MarcadoresEnCadena.de(self.user_ids)

    def meter(self, jugador: JugadorDePartida, jugadores_por_partida: int) -> None:
        """Mete a un jugador al final, si cabe; la cadena se rehace."""
        self._sin_empezar()
        if jugador.user_id in self.user_ids:
            raise PartidaInvalidaError("Ese jugador ya está en la partida.")
        if len(self._jugadores) >= jugadores_por_partida:
            raise PartidaInvalidaError("La partida está llena.")
        self._jugadores = [*self._jugadores, jugador]
        self._tarjetas[jugador.user_id] = EstadoDeTarjeta.JUGANDO
        self._marcadores = MarcadoresEnCadena.de(self.user_ids)

    def cambiar_marcadores(self, marcadores: Mapping[UserId, UserId]) -> None:
        """Otra asignación de marcadores, si es válida (D12)."""
        self._sin_empezar()
        MarcadoresEnCadena.validar(self.user_ids, marcadores)
        self._marcadores = dict(marcadores)

    def renumerar(self, numero: int) -> None:
        """Otro número de salida: la hora sale de él."""
        self._sin_empezar()
        self._comprobar_numero(numero)
        self._numero = numero

    def recalcular(self, jugadores: Sequence[JugadorDePartida]) -> None:
        """La foto nueva de los mismos jugadores (otro campo, otro hándicap fijado)."""
        self._sin_empezar()
        if sorted(str(j.user_id) for j in jugadores) != sorted(str(u) for u in self.user_ids):
            raise PartidaInvalidaError("Recalcular no cambia quién juega.")
        por_id = {j.user_id: j for j in jugadores}
        self._jugadores = [por_id[u] for u in self.user_ids]

    # ==================== La partida en juego (PR 5) ====================

    def empezar(self) -> None:
        """El primer golpe la pone en juego (P2); si ya lo estaba, nada."""
        if self._estado == EstadoPartida.SCHEDULED:
            self._estado = EstadoPartida.IN_PROGRESS

    def entregar(self, user_id: UserId) -> None:
        """
        Entrega su tarjeta (P3); con todas cerradas, la partida acaba.

        Que todos sus hoyos estén validados lo mira quien llama (P4).
        """
        self._cerrar_tarjeta(user_id, EstadoDeTarjeta.ENTREGADA)

    def retirar(self, user_id: UserId) -> None:
        """Lo deja a medias: NR en Medal; en Stableford cuenta lo jugado (P6)."""
        self._cerrar_tarjeta(user_id, EstadoDeTarjeta.RETIRADO)

    def no_presentado(self, user_id: UserId) -> None:
        """No se presentó (P6): también antes de que la partida empiece."""
        self._de_la_partida(user_id)
        if self._tarjetas[user_id] != EstadoDeTarjeta.JUGANDO:
            raise TarjetaCerradaError("Esa tarjeta ya está cerrada.")
        self._tarjetas[user_id] = EstadoDeTarjeta.NO_PRESENTADO
        self._acabar_si_no_queda_nadie()

    def reabrir_tarjeta(self, user_id: UserId) -> None:
        """El organizador la vuelve a abrir para corregirla (P9)."""
        self._de_la_partida(user_id)
        self._tarjetas[user_id] = EstadoDeTarjeta.JUGANDO
        if self._estado == EstadoPartida.COMPLETED:
            self._estado = EstadoPartida.IN_PROGRESS

    def cerrar(self, completas: Collection[UserId], sin_hoyos: Collection[UserId] = ()) -> None:
        """
        El organizador cierra la partida (P3, la red). Las tarjetas aún en juego:
        completas, entregadas; sin ningún hoyo validado, no presentado; a medias,
        retirado. Las ya cerradas se quedan como estaban.
        """
        for user_id, estado in self._tarjetas.items():
            if estado != EstadoDeTarjeta.JUGANDO:
                continue
            if user_id in completas:
                self._tarjetas[user_id] = EstadoDeTarjeta.ENTREGADA
            elif user_id in sin_hoyos:
                self._tarjetas[user_id] = EstadoDeTarjeta.NO_PRESENTADO
            else:
                self._tarjetas[user_id] = EstadoDeTarjeta.RETIRADO
        self._estado = EstadoPartida.COMPLETED

    def _cerrar_tarjeta(self, user_id: UserId, estado: EstadoDeTarjeta) -> None:
        self._de_la_partida(user_id)
        if not self.empezada:
            raise PartidaNoEmpezadaError("La partida aún no ha empezado.")
        if self._tarjetas[user_id] != EstadoDeTarjeta.JUGANDO:
            raise TarjetaCerradaError("Esa tarjeta ya está cerrada.")
        self._tarjetas[user_id] = estado
        self._acabar_si_no_queda_nadie()

    def _acabar_si_no_queda_nadie(self) -> None:
        if self.empezada and EstadoDeTarjeta.JUGANDO not in self._tarjetas.values():
            self._estado = EstadoPartida.COMPLETED

    def _de_la_partida(self, user_id: UserId) -> None:
        if user_id not in self._tarjetas:
            raise PartidaInvalidaError("Ese jugador no está en la partida.")

    # ==================== Consultas ====================

    @property
    def estados_de_tarjeta(self) -> dict[UserId, EstadoDeTarjeta]:
        return dict(self._tarjetas)

    def may_mark(self, scorer_id: UserId, marked_id: UserId) -> bool:
        """Si `scorer_id` le apunta los golpes a `marked_id`: solo a quien le toca."""
        return self._marcadores.get(scorer_id) == marked_id

    @property
    def id(self) -> PartidaId:
        return self._id

    @property
    def competition_id(self) -> CompetitionId:
        return self._competition_id

    @property
    def round_id(self) -> RoundId:
        return self._round_id

    @property
    def numero(self) -> int:
        return self._numero

    @property
    def jugadores(self) -> tuple[JugadorDePartida, ...]:
        return tuple(self._jugadores)

    @property
    def user_ids(self) -> list[UserId]:
        return [j.user_id for j in self._jugadores]

    @property
    def marcadores(self) -> dict[UserId, UserId]:
        """marcador -> marcado."""
        return dict(self._marcadores)

    @property
    def estado(self) -> EstadoPartida:
        return self._estado

    @property
    def empezada(self) -> bool:
        return self._estado.empezada()

    @property
    def incompleta(self) -> bool:
        """De un solo jugador: sin marcador, hasta que el organizador la arregle (D4)."""
        return len(self._jugadores) < MIN_PARA_MARCAR

    # ==================== Reglas ====================

    def _sin_empezar(self) -> None:
        if self.empezada:
            raise PartidaEmpezadaError("La partida ya ha salido y no se puede cambiar.")

    @staticmethod
    def _comprobar_numero(numero: int) -> None:
        if numero < 1:
            raise PartidaInvalidaError("Las partidas se numeran desde 1.")

    @staticmethod
    def _comprobar_jugadores(jugadores: Sequence[JugadorDePartida]) -> None:
        if not 1 <= len(jugadores) <= MAX_JUGADORES:
            raise PartidaInvalidaError(f"Una partida es de 1 a {MAX_JUGADORES} jugadores.")
        if len({j.user_id for j in jugadores}) != len(jugadores):
            raise PartidaInvalidaError("Un jugador solo puede estar una vez en la partida.")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Partida) and self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)
