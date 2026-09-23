"""
Envelope - El sobre de un capitan (FE #655).

Asi lo hace la Ryder de verdad, y por eso se hace asi aqui: cada capitan
entrega una lista ORDENADA de los suyos —jugadores en individuales, parejas en
los formatos de dos— sin ver la del otro, y los enfrentamientos salen de cruzar
las dos listas POR POSICION: el primero contra el primero. El azar esta en no
saber que hizo el rival, no en un sorteo.

Dos decisiones del dueno del producto (20 sep):

- **Juegan todos.** Aqui no se descansa: si sois doce, salen seis parejas y no
  hay a quien sentar. Un sobre al que le falte alguien del equipo no vale.
- **Lo que falte al vencer el plazo lo rellena la aplicacion**, y lo que hace
  la aplicacion se puede seguir editando: automatico no es definitivo.
"""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from src.modules.user.domain.value_objects.user_id import UserId

from ..value_objects.competition_id import CompetitionId
from ..value_objects.envelope_id import EnvelopeId
from ..value_objects.match_format import MatchFormat
from ..value_objects.round_id import RoundId

EQUIPOS = ("A", "B")


class EnvelopeAlreadyRevealedError(Exception):
    """El sobre ya se abrio: cambiarlo seria rehacer el sorteo a escondidas."""

    pass


class EmptyEnvelopeError(Exception):
    """El sobre no lleva nada dentro."""

    pass


class PlayerNotInTeamError(Exception):
    """Ese jugador no es de este equipo."""

    pass


class TeamNotFullyEnteredError(Exception):
    """Falta alguien del equipo, y aqui juegan todos."""

    pass


class Envelope:
    """El sobre de un equipo para una sesion."""

    def __init__(
        self,
        id: EnvelopeId,
        competition_id: CompetitionId,
        round_id: RoundId,
        team: str,
        match_format: MatchFormat,
        entries: Sequence[Sequence[UserId]] = (),
        submitted_at: datetime | None = None,
        submitted_by: UserId | None = None,
        automatic: bool = False,
        revealed: bool = False,
    ):
        if team not in EQUIPOS:
            raise ValueError(f"El equipo tiene que ser A o B, no {team!r}")
        self._id = id
        self._competition_id = competition_id
        self._round_id = round_id
        self._team = team
        self._match_format = match_format
        self._entries: tuple[tuple[UserId, ...], ...] = tuple(tuple(f) for f in entries)
        self._submitted_at = submitted_at
        self._submitted_by = submitted_by
        self._automatic = automatic
        self._revealed = revealed

    @classmethod
    def create(
        cls,
        competition_id: CompetitionId,
        round_id: RoundId,
        team: str,
        match_format: MatchFormat,
    ) -> "Envelope":
        """Un sobre vacio, a la espera de que el capitan lo rellene."""
        return cls(
            id=EnvelopeId.generate(),
            competition_id=competition_id,
            round_id=round_id,
            team=team,
            match_format=match_format,
        )

    # ==================== Consultas ====================

    @property
    def id(self) -> EnvelopeId:
        """El identificador del sobre."""
        return self._id

    @property
    def competition_id(self) -> CompetitionId:
        """La competición."""
        return self._competition_id

    @property
    def round_id(self) -> RoundId:
        """La sesión a la que pertenece."""
        return self._round_id

    @property
    def team(self) -> str:
        """El equipo que lo entrega: A o B."""
        return self._team

    @property
    def match_format(self) -> MatchFormat:
        """El formato de la sesión, que decide si las filas son de uno o de dos."""
        return self._match_format

    @property
    def entries(self) -> tuple[tuple[UserId, ...], ...]:
        """Las filas, en el orden que decidió el capitán."""
        return self._entries

    @property
    def submitted_at(self) -> datetime | None:
        """Cuándo se entregó."""
        return self._submitted_at

    @property
    def submitted_by(self) -> UserId | None:
        """Quién lo entregó, o None si lo rellenó la aplicación."""
        return self._submitted_by

    @property
    def automatic(self) -> bool:
        """Si lo rellenó la aplicación al vencer el plazo."""
        return self._automatic

    def is_submitted(self) -> bool:
        """Si ya hay algo dentro."""
        return bool(self._entries)

    def is_sealed(self) -> bool:
        """Si todavía está cerrado. Ver la lista del rival antes es el juego entero."""
        return not self._revealed

    def players_per_row(self) -> int:
        """Cuántos jugadores lleva cada fila: uno en individuales, dos en parejas."""
        return 1 if self._match_format == MatchFormat.SINGLES else 2

    # ==================== Acciones ====================

    def submit(
        self,
        entries: Sequence[Sequence[UserId]],
        equipo: Sequence[UserId],
        por: UserId,
        ahora: datetime,
    ) -> None:
        """Entrega —o corrige— la lista del capitán.

        Args:
            entries: Las filas, en orden
            equipo: Los jugadores de este equipo, para comprobar que están todos
            por: Quién lo entrega
            ahora: La hora del servidor

        Raises:
            EnvelopeAlreadyRevealedError: Si ya se abrió
            ValueError: Si una fila no tiene el tamaño del formato o alguien se repite
            PlayerNotInTeamError: Si alguien no es de este equipo
            TeamNotFullyEnteredError: Si falta alguien del equipo
        """
        self._comprobar_cerrado()
        self._validar(entries, equipo)
        self._entries = tuple(tuple(fila) for fila in entries)
        self._submitted_at = ahora
        self._submitted_by = por
        self._automatic = False

    def fill(
        self, jugadores: Sequence[tuple[UserId, Decimal | int | float]], ahora: datetime
    ) -> None:
        """Rellena el sobre que el capitán no entregó a tiempo (decidido el 20 sep).

        En individuales, por hándicap de menor a mayor, que es el criterio que
        la aplicación usa para todo lo demás. En parejas junta al mejor con el
        peor: parejas equilibradas y no una fuerte y otra floja, igual que el
        reparto automático de equipos.

        **No pisa lo que el capitán ya entregó**: el que llegó a tiempo no se
        queda sin su lista por culpa del que se olvidó.
        """
        self._comprobar_cerrado()
        if self.is_submitted():
            return

        ordenados = [uid for uid, _ in sorted(jugadores, key=lambda par: Decimal(str(par[1])))]
        if self.players_per_row() == 1:
            self._entries = tuple((uid,) for uid in ordenados)
        else:
            # El mejor con el peor: primero contra último, y hacia dentro
            self._entries = tuple(
                (ordenados[i], ordenados[len(ordenados) - 1 - i])
                for i in range(len(ordenados) // 2)
            )
        self._submitted_at = ahora
        self._submitted_by = None
        self._automatic = True

    def reveal(self) -> None:
        """Abre el sobre. A partir de aquí ya no se toca.

        Raises:
            ValueError: Si está vacío: no hay nada que abrir
        """
        if not self.is_submitted():
            raise EmptyEnvelopeError("El sobre está vacío: no hay nada que abrir")
        self._revealed = True

    @staticmethod
    def pair_up(
        sobre_a: "Envelope", sobre_b: "Envelope"
    ) -> list[tuple[tuple[UserId, ...], tuple[UserId, ...]]]:
        """Cruza los dos sobres por posición: el primero contra el primero.

        Con equipos desiguales —el draft admite uno de diferencia— juegan los
        que se pueden emparejar; el que sobra se queda sin rival.

        Raises:
            ValueError: Si no son de la misma sesión
        """
        if sobre_a.round_id != sobre_b.round_id:
            raise ValueError("Los dos sobres tienen que ser de la misma ronda")
        return list(zip(sobre_a.entries, sobre_b.entries, strict=False))

    # ==================== Interno ====================

    def _comprobar_cerrado(self) -> None:
        if self._revealed:
            raise EnvelopeAlreadyRevealedError("El sobre ya se abrió")

    def _validar(self, entries: Sequence[Sequence[UserId]], equipo: Sequence[UserId]) -> None:
        if not entries:
            # Con el equipo vacio, «faltan» tambien sale vacio y esto pasaria:
            # un 200 que no guarda nada y deja al capitan creyendo que entrego
            raise EmptyEnvelopeError("El sobre está vacío: pon el orden de tu equipo")
        por_fila = self.players_per_row()
        for fila in entries:
            if len(fila) != por_fila:
                raise ValueError(
                    "En individuales cada fila es de uno"
                    if por_fila == 1
                    else "En parejas cada fila son dos jugadores"
                )

        puestos = [uid for fila in entries for uid in fila]
        if len(set(puestos)) != len(puestos):
            raise ValueError("Hay jugadores repetidos: nadie juega dos veces la misma sesión")

        del_equipo = set(equipo)
        fuera = set(puestos) - del_equipo
        if fuera:
            raise PlayerNotInTeamError("Hay jugadores que no son de este equipo")

        # Juegan todos: aqui no se descansa (20 sep). Con un numero impar de
        # jugadores para el formato, el que sobra se queda sin fila, y eso se
        # ve al cruzar los dos sobres, no aqui
        faltan = del_equipo - set(puestos)
        if len(faltan) >= por_fila:
            raise TeamNotFullyEnteredError(
                f"Faltan {len(faltan)} jugadores del equipo, y aquí juegan todos"
            )
