"""
Draft - La sala donde los capitanes eligen equipo (FE #653).

Disenada con el dueno del producto el 22 sep: entran los dos capitanes, se
sortea delante de ellos quien empieza, el de turno tiene un minuto y al elegir
salta al otro, hasta que no quede nadie. El resto lo ve en directo.

El reloj es del SERVIDOR, como en la anotacion (BE #305). Dos moviles contando
su minuto se desincronizan y acaban eligiendo al mismo jugador dos veces, asi
que aqui no hay ningun proceso de fondo: el turno agotado se resuelve cuando
alguien mira la sala, igual que la anotacion abre cuando llega el primer golpe.

Los capitanes NO entran al draft: nombrarlos ya los fijo en su equipo
(RyderCupAm#320). La lista de elegibles la trae el caso de uso, porque las
inscripciones son otro agregado.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.modules.user.domain.value_objects.user_id import UserId

from ..services.snake_draft_service import PlayerForDraft
from ..value_objects.competition_id import CompetitionId
from ..value_objects.draft_id import DraftId
from ..value_objects.draft_status import DraftStatus

EQUIPOS = ("A", "B")
SEGUNDOS_POR_TURNO = 60


class DraftNotRunningError(Exception):
    """La sala no esta en el punto que esa accion necesita."""

    pass


class NotYourTurnError(Exception):
    """Elige el capitan del equipo al que le toca, y nadie mas."""

    pass


class PlayerAlreadyPickedError(Exception):
    """Ese jugador ya no se puede elegir: o esta cogido, o no estaba en la lista."""

    pass


@dataclass(frozen=True)
class DraftPick:
    """Una eleccion: quien, para que equipo, en que orden y si la hizo la app."""

    user_id: UserId
    team: str
    order: int
    automatic: bool = False


class Draft:
    """La sala de draft de una competicion."""

    def __init__(
        self,
        id: DraftId,
        competition_id: CompetitionId,
        team_a_captain_id: UserId,
        team_b_captain_id: UserId,
        status: DraftStatus = DraftStatus.PENDING,
        first_pick: str | None = None,
        current_team: str | None = None,
        turn_started_at: datetime | None = None,
        picks: Sequence[DraftPick] = (),
        seconds_per_turn: int = SEGUNDOS_POR_TURNO,
    ):
        self._id = id
        self._competition_id = competition_id
        self._team_a_captain_id = team_a_captain_id
        self._team_b_captain_id = team_b_captain_id
        self._status = status
        self._first_pick = first_pick
        self._current_team = current_team
        self._turn_started_at = turn_started_at
        self._picks: tuple[DraftPick, ...] = tuple(picks)
        self._seconds_per_turn = seconds_per_turn

    @classmethod
    def create(
        cls,
        competition_id: CompetitionId,
        team_a_captain_id: UserId,
        team_b_captain_id: UserId,
    ) -> "Draft":
        """Abre la sala, a la espera de que el organizador lance el sorteo."""
        return cls(
            id=DraftId.generate(),
            competition_id=competition_id,
            team_a_captain_id=team_a_captain_id,
            team_b_captain_id=team_b_captain_id,
        )

    # ==================== Consultas ====================

    @property
    def id(self) -> DraftId:
        """El identificador de la sala."""
        return self._id

    @property
    def competition_id(self) -> CompetitionId:
        """La competición a la que pertenece."""
        return self._competition_id

    @property
    def status(self) -> DraftStatus:
        """En qué punto está la sala."""
        return self._status

    @property
    def first_pick(self) -> str | None:
        """El equipo que salió en el sorteo, o None si no se ha lanzado."""
        return self._first_pick

    @property
    def current_team(self) -> str | None:
        """El equipo al que le toca elegir, o None si no hay turno."""
        return self._current_team

    @property
    def turn_started_at(self) -> datetime | None:
        """Cuándo empezó el turno de ahora, para contar el minuto."""
        return self._turn_started_at

    @property
    def picks(self) -> tuple[DraftPick, ...]:
        """Las elecciones hechas, en orden."""
        return self._picks

    @property
    def seconds_per_turn(self) -> int:
        """Lo que dura un turno. Se guarda para poder cambiarlo sin migrar."""
        return self._seconds_per_turn

    @property
    def team_a_captain_id(self) -> UserId:
        """El capitán del equipo A."""
        return self._team_a_captain_id

    @property
    def team_b_captain_id(self) -> UserId:
        """El capitán del equipo B."""
        return self._team_b_captain_id

    def teams(self) -> tuple[list[UserId], list[UserId]]:
        """Los dos equipos tal como van: cada capitán y detrás sus elegidos.

        También a medias, que es lo que la ficha enseña en directo.
        """
        equipo_a = [self._team_a_captain_id]
        equipo_b = [self._team_b_captain_id]
        for pick in self._picks:
            (equipo_a if pick.team == "A" else equipo_b).append(pick.user_id)
        return equipo_a, equipo_b

    def check_turn(self, user_id: UserId) -> None:
        """Comprueba que le toca elegir a ese capitán.

        Raises:
            DraftNotRunningError: Si la sala no está en marcha
            NotYourTurnError: Si no es el capitán del equipo de turno
        """
        # Antes que el turno: en una sala terminada no hay turno de nadie, y
        # decir «no es tu turno» mandaría al capitán a esperar el suyo
        self._comprobar_en_marcha()
        if user_id != self._captain_of(self._current_team):
            raise NotYourTurnError("No es tu turno")

    @property
    def turn_deadline(self) -> datetime | None:
        """Cuándo se le acaba el minuto al turno de ahora, o None si no hay turno.

        El turno siguiente empieza AQUÍ, no cuando alguien mire la sala: si no,
        una sala que nadie mira en diez minutos resolvería un solo turno por
        vistazo, y el capitán que llega tarde se encontraría el reloj parado
        esperándole.
        """
        if self._turn_started_at is None:
            return None
        return self._turn_started_at + timedelta(seconds=self._seconds_per_turn)

    def turn_expired(self, ahora: datetime) -> bool:
        """Indica si al turno de ahora se le acabó el minuto.

        Sin turno —esperando el sorteo o terminada— no expira nada.
        """
        if self._status != DraftStatus.IN_PROGRESS or self._turn_started_at is None:
            return False
        return (ahora - self._turn_started_at).total_seconds() >= self._seconds_per_turn

    # ==================== Acciones ====================

    def start(self, first_pick: str, ahora: datetime) -> None:
        """Empieza el draft con el equipo que salió en el sorteo.

        Raises:
            ValueError: Si el equipo no es A ni B
            DraftNotRunningError: Si ya había empezado
        """
        if first_pick not in EQUIPOS:
            raise ValueError(f"El equipo tiene que ser A o B, no {first_pick!r}")
        if self._status != DraftStatus.PENDING:
            # Volver a sortear a mitad cambiaría el orden con elecciones hechas
            raise DraftNotRunningError("El draft ya había empezado")

        self._status = DraftStatus.IN_PROGRESS
        self._first_pick = first_pick
        self._current_team = first_pick
        self._turn_started_at = ahora

    def pick(self, player: UserId, elegibles: Sequence[PlayerForDraft], ahora: datetime) -> None:
        """Elige a un jugador para el equipo de turno.

        Quién puede pedirlo lo comprueba el caso de uso con `check_turn`: la app
        también elige por un capitán cuando se le acaba el minuto.

        Raises:
            DraftNotRunningError: Si la sala no está en marcha
            PlayerAlreadyPickedError: Si ya está cogido o no estaba en la lista
        """
        self._comprobar_en_marcha()
        if player not in self._disponibles(elegibles):
            raise PlayerAlreadyPickedError("Ese jugador ya no se puede elegir")

        self._anotar(player, automatic=False)
        self._pasar_turno(elegibles, ahora)

    def pick_for_expired_turn(self, elegibles: Sequence[PlayerForDraft], ahora: datetime) -> UserId:
        """Elige por el capitán al que se le acabó el minuto (decidido el 20 sep).

        El hándicap más bajo de los que quedan, que es el criterio que ya usa el
        reparto automático. El draft nunca se queda parado esperando a nadie.

        Returns:
            El jugador que eligió la aplicación
        """
        self._comprobar_en_marcha()
        disponibles = [p for p in elegibles if p.user_id in self._disponibles(elegibles)]
        if not disponibles:
            raise DraftNotRunningError("No queda nadie por elegir")

        elegido = min(disponibles, key=lambda p: p.handicap).user_id
        self._anotar(elegido, automatic=True)
        self._pasar_turno(elegibles, ahora)
        return elegido

    # ==================== Interno ====================

    def _captain_of(self, team: str | None) -> UserId | None:
        if team == "A":
            return self._team_a_captain_id
        if team == "B":
            return self._team_b_captain_id
        return None

    def _disponibles(self, elegibles: Sequence[PlayerForDraft]) -> set[UserId]:
        cogidos = {pick.user_id for pick in self._picks}
        return {p.user_id for p in elegibles} - cogidos

    def _comprobar_en_marcha(self) -> None:
        if self._status != DraftStatus.IN_PROGRESS:
            raise DraftNotRunningError(f"El draft no está en marcha: {self._status.value}")

    def _anotar(self, player: UserId, automatic: bool) -> None:
        # En marcha siempre hay equipo de turno: `_comprobar_en_marcha` ya pasó
        turno = self._current_team
        if turno is None:
            raise DraftNotRunningError("No hay ningún turno abierto")
        self._picks = (
            *self._picks,
            DraftPick(
                user_id=player,
                team=turno,
                order=len(self._picks) + 1,
                automatic=automatic,
            ),
        )

    def _pasar_turno(self, elegibles: Sequence[PlayerForDraft], ahora: datetime) -> None:
        """Al otro capitán, o cierra la sala si ya no queda nadie.

        Si solo queda uno, no hay nada que elegir (decidido el 24 sep): va al
        equipo al que le toca y la sala termina, sin que nadie espere su minuto.
        """
        disponibles = self._disponibles(elegibles)
        if disponibles:
            self._current_team = "B" if self._current_team == "A" else "A"
            self._turn_started_at = ahora
        if len(disponibles) == 1:
            (ultimo,) = disponibles
            self._anotar(ultimo, automatic=True)
            disponibles = set()
        if not disponibles:
            self._status = DraftStatus.COMPLETED
            self._current_team = None
            self._turn_started_at = None
