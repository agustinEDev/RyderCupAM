"""
MatchGenerationBlock - Por que una sesion con los sobres abiertos no tiene partidos (BE #361).

Los partidos se crean al abrirse los sobres, y eso ocurre dentro de la lectura
que hace cualquiera de la docena de moviles que miran la pantalla. Si no se
pueden crear —a un jugador le falta el sexo en su perfil, el campo no tiene el
color de barras que se le asigno—, la sesion se queda con los sobres abiertos y
sin partidos. Esto es lo que queda apuntado para que alguien lo vea y lo
arregle: el motivo, y **a quien le falta que**, no solo que fallo.
"""

from dataclasses import dataclass, field
from datetime import datetime

from src.modules.user.domain.value_objects.user_id import UserId

# Los motivos. Son claves y no frases: el frontend las pone en el idioma de la
# pantalla, que el backend no conoce (BE #360)
PLAYERS_WITHOUT_TEE = "PLAYERS_WITHOUT_TEE"
NOT_ENOUGH_PLAYERS = "NOT_ENOUGH_PLAYERS"
NO_TEAMS = "NO_TEAMS"
NO_GOLF_COURSE = "NO_GOLF_COURSE"
UNEXPECTED = "UNEXPECTED"
# Se abrieron con las inscripciones reabiertas: al cerrarlas, «Generar» los
# crea con esos sobres (revisión de la FE #711)
ENROLLMENT_OPEN = "ENROLLMENT_OPEN"

# Lo que le falta a cada jugador
MISSING_GENDER = "GENDER"
MISSING_TEE_COLOR = "TEE_COLOR"


@dataclass(frozen=True)
class BlockedPlayer:
    """Un jugador por el que no se pueden generar los partidos."""

    user_id: UserId
    # El nombre de ese momento: el aviso tiene que poder pintarse sin volver a
    # preguntar por nadie, y en el panel se lee de varias competiciones a la vez
    name: str
    missing: str
    # El color que se le asigno, cuando lo que falta es ese color en el campo
    tee_color: str | None = None


@dataclass(frozen=True)
class MatchGenerationBlock:
    """El motivo por el que la sesion se quedo sin partidos."""

    reason: str
    players: tuple[BlockedPlayer, ...] = field(default_factory=tuple)
    at: datetime | None = None

    def to_dict(self) -> dict:
        """Para guardarlo en una columna JSON."""
        return {
            "reason": self.reason,
            "players": [
                {
                    "user_id": str(p.user_id.value),
                    "name": p.name,
                    "missing": p.missing,
                    "tee_color": p.tee_color,
                }
                for p in self.players
            ],
            "at": self.at.isoformat() if self.at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MatchGenerationBlock":
        """Lo contrario de `to_dict`."""
        return cls(
            reason=data["reason"],
            players=tuple(
                BlockedPlayer(
                    user_id=UserId(p["user_id"]),
                    name=p.get("name", ""),
                    missing=p["missing"],
                    tee_color=p.get("tee_color"),
                )
                for p in data.get("players", [])
            ),
            at=datetime.fromisoformat(data["at"]) if data.get("at") else None,
        )
