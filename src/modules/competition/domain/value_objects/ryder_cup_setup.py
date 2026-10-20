"""
RyderCupSetup Value Object - Lo que es solo de la Ryder Cup (RyderCupAM#251).

Decidido con el dueño del producto el 1 oct 2026: lo común a las dos
modalidades (inscripción, campos, rondas, anotación) se comparte, y lo que es de
una sola va en su propia pieza. Equipos, modo de montaje, reparto y capitanes
son de la Ryder Cup: un Stableford no tiene esta pieza.

**Es inmutable a propósito.** Se guarda en las mismas columnas de
`competitions` con `composite()`, y SQLAlchemy no ve un cambio hecho DENTRO de
un composite: lo perdería sin avisar. Por eso cada cambio devuelve una pieza
nueva, y quien la tiene la sustituye entera; un cambio por dentro lanza
`FrozenInstanceError` en vez de perderse.

Aquí viven las reglas que solo dependen de la pieza. Las que además tocan el
ciclo de vida del torneo (en qué estado se nombra un capitán, cerrar las
inscripciones al nombrarlos) siguen en `Competition`, que le pide la regla a la
pieza y la sustituye.
"""

from dataclasses import dataclass, replace
from typing import Self

from src.modules.user.domain.value_objects.user_id import UserId

from .setup_mode import SetupMode
from .team_assignment import TeamAssignment

TEAMS = ("A", "B")


class CaptainMissingError(Exception):
    """Hay un solo capitan: el otro se dio de baja y falta nombrarlo."""

    pass


class CaptainOnWrongTeamError(Exception):
    """Un capitan no esta en el equipo que capitanea."""

    pass


@dataclass(frozen=True)
class RyderCupSetup:
    """Equipos, modo de montaje, reparto y capitanes de una Ryder Cup."""

    team_1_name: str
    team_2_name: str
    setup_mode: SetupMode
    team_assignment: TeamAssignment
    team_a_captain_id: UserId | None = None
    team_b_captain_id: UserId | None = None
    team_a_vice_captain_id: UserId | None = None
    team_b_vice_captain_id: UserId | None = None

    # ------------------------------------------------------------------
    # Creación
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        team_1_name: str | None,
        team_2_name: str | None,
        setup_mode: SetupMode = SetupMode.RYDER_CUP,
    ) -> Self:
        """Una Ryder nueva, sin capitanes. El reparto sale del modo (FE #695)."""
        nombre_1, nombre_2 = cls._validate_team_names(team_1_name, team_2_name)
        return cls(
            team_1_name=nombre_1,
            team_2_name=nombre_2,
            setup_mode=setup_mode,
            team_assignment=cls._assignment_for(setup_mode),
        )

    @staticmethod
    def _assignment_for(setup_mode: SetupMode) -> TeamAssignment:
        """Como se reparten los equipos, segun el modo (FE #695, 22 sep).

        El reparto dejo de preguntarse aparte: un campo propio podia
        contradecir al modo —«todo automatico» con el reparto a mano—, y la
        ficha devolvia las dos cosas.

        En estilo RyderCup los equipos salen del draft, o se ponen a mano: lo
        que no puede es repartirlos la aplicacion a espaldas del organizador.
        """
        return (
            TeamAssignment.AUTOMATIC if setup_mode == SetupMode.AUTOMATIC else TeamAssignment.MANUAL
        )

    @staticmethod
    def _validate_team_names(team_1_name: str | None, team_2_name: str | None) -> tuple[str, str]:
        """Los dos con nombre, y distintos: la regla es de la pareja. Los devuelve ya comprobados."""
        if not team_1_name or not team_1_name.strip():
            raise ValueError("El nombre del equipo 1 no puede estar vacío")
        if not team_2_name or not team_2_name.strip():
            raise ValueError("El nombre del equipo 2 no puede estar vacío")
        if team_1_name.strip().lower() == team_2_name.strip().lower():
            raise ValueError("Los nombres de los equipos deben ser diferentes")
        return team_1_name, team_2_name

    # ------------------------------------------------------------------
    # Equipos y modo
    # ------------------------------------------------------------------

    def with_team_names(self, team_1_name: str | None, team_2_name: str | None) -> Self:
        """Cambia uno o los dos nombres; cambiar uno solo también se mira contra el otro."""
        nuevo_1, nuevo_2 = self._validate_team_names(
            team_1_name if team_1_name is not None else self.team_1_name,
            team_2_name if team_2_name is not None else self.team_2_name,
        )
        return replace(self, team_1_name=nuevo_1, team_2_name=nuevo_2)

    def with_setup_mode(self, setup_mode: SetupMode) -> Self:
        """El modo manda: si cambia, el reparto sale de él."""
        return replace(
            self, setup_mode=setup_mode, team_assignment=self._assignment_for(setup_mode)
        )

    def with_team_assignment(self, team_assignment: TeamAssignment) -> Self:
        return replace(self, team_assignment=team_assignment)

    # ------------------------------------------------------------------
    # Capitanes
    # ------------------------------------------------------------------

    @staticmethod
    def check_team(team: str) -> None:
        """Solo hay dos equipos: A y B."""
        if team not in TEAMS:
            raise ValueError(f"El equipo tiene que ser A o B, no {team!r}")

    def captain(self, team: str) -> UserId | None:
        """El capitán de ese equipo; valida antes que el equipo sea A o B."""
        self.check_team(team)
        return self.team_a_captain_id if team == "A" else self.team_b_captain_id

    def vice_captain(self, team: str) -> UserId | None:
        """El subcapitán de ese equipo; valida antes que el equipo sea A o B."""
        self.check_team(team)
        return self.team_a_vice_captain_id if team == "A" else self.team_b_vice_captain_id

    def is_captain_of(self, team: str, user_id: UserId) -> bool:
        """Indica si ese jugador capitanea ese equipo ("A" o "B")."""
        return self.captain(team) == user_id

    def with_captains(self, team_a: UserId, team_b: UserId) -> Self:
        return replace(self, team_a_captain_id=team_a, team_b_captain_id=team_b)

    def with_captain(self, team: str, player: UserId | None) -> Self:
        """Pone el capitán de un equipo; si era su subcapitán, deja ese puesto libre."""
        self.check_team(team)
        if team == "A":
            pieza = replace(self, team_a_captain_id=player)
        else:
            pieza = replace(self, team_b_captain_id=player)
        if player is not None and pieza.vice_captain(team) == player:
            pieza = pieza.with_vice_captain(team, None)
        return pieza

    def with_vice_captain(self, team: str, player: UserId | None) -> Self:
        self.check_team(team)
        if team == "A":
            return replace(self, team_a_vice_captain_id=player)
        return replace(self, team_b_vice_captain_id=player)

    def without_vice_captains(self) -> Self:
        """Al repartir de nuevo, los subcapitanes quedan libres: el equipo ha cambiado."""
        return replace(self, team_a_vice_captain_id=None, team_b_vice_captain_id=None)

    def after_withdrawal(self, user_id: UserId) -> Self | None:
        """Lo que pasa con los capitanes cuando un jugador se da de baja.

        Si se va un capitán, asciende su subcapitán; sin subcapitán, el puesto
        queda libre. Si se va un subcapitán, su puesto queda libre.

        Returns:
            La pieza nueva, o None si no era capitán ni subcapitán
        """
        for team in TEAMS:
            if user_id == self.captain(team):
                ascendido = self.vice_captain(team)
                return self.with_vice_captain(team, None).with_captain(team, ascendido)
            if user_id == self.vice_captain(team):
                return self.with_vice_captain(team, None)
        return None

    def captains_for_team_split(self) -> tuple[UserId, UserId] | None:
        """Los capitanes que quedan fijos al repartir equipos.

        Sin ninguno, None: el reparto de siempre, porque el flujo viejo convive
        con el nuevo durante la transicion. Con uno solo —el otro se dio de
        baja— no se reparte cojo: un equipo quedaria sin capitan.

        Raises:
            CaptainMissingError: Si solo hay uno
        """
        if self.team_a_captain_id is None and self.team_b_captain_id is None:
            return None
        if self.team_a_captain_id is None or self.team_b_captain_id is None:
            raise CaptainMissingError(
                "Falta un capitán: se dio de baja. Nombra a otro antes de repartir equipos"
            )
        return self.team_a_captain_id, self.team_b_captain_id

    def check_captains_placement(
        self, team_a_player_ids: list[UserId], team_b_player_ids: list[UserId]
    ) -> None:
        """Comprueba que cada capitan esta en el equipo que capitanea.

        Raises:
            CaptainMissingError: Si solo hay uno
            CaptainOnWrongTeamError: Si alguno no esta en su equipo
        """
        capitanes = self.captains_for_team_split()
        if capitanes is None:
            return
        capitan_a, capitan_b = capitanes
        if capitan_a not in team_a_player_ids or capitan_b not in team_b_player_ids:
            raise CaptainOnWrongTeamError("Cada capitán tiene que estar en el equipo que capitanea")

    # ------------------------------------------------------------------
    # Columnas (composite de SQLAlchemy)
    # ------------------------------------------------------------------

    def __composite_values__(self) -> tuple:
        """En el orden de `from_columns`: así se guarda en `competitions`."""
        return (
            self.team_1_name,
            self.team_2_name,
            self.setup_mode,
            self.team_assignment,
            self.team_a_captain_id,
            self.team_b_captain_id,
            self.team_a_vice_captain_id,
            self.team_b_vice_captain_id,
        )

    @classmethod
    def from_columns(
        cls,
        team_1_name: str | None,
        team_2_name: str | None,
        setup_mode: object,
        team_assignment: object,
        team_a_captain_id: UserId | None,
        team_b_captain_id: UserId | None,
        team_a_vice_captain_id: UserId | None,
        team_b_vice_captain_id: UserId | None,
    ) -> Self | None:
        """
        Reconstruye la pieza al leer. Sin nombres de equipo no hay Ryder: None.

        No valida los nombres: lo guardado ya pasó la validación al crearse, y
        una lectura no debe tumbar la carga de un torneo.
        """
        if team_1_name is None and team_2_name is None:
            return None
        return cls(
            team_1_name=team_1_name or "",
            team_2_name=team_2_name or "",
            setup_mode=SetupMode(str(setup_mode)) if setup_mode else SetupMode.RYDER_CUP,
            team_assignment=(
                TeamAssignment(str(team_assignment)) if team_assignment else TeamAssignment.MANUAL
            ),
            team_a_captain_id=team_a_captain_id,
            team_b_captain_id=team_b_captain_id,
            team_a_vice_captain_id=team_a_vice_captain_id,
            team_b_vice_captain_id=team_b_vice_captain_id,
        )
