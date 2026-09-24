"""
DTO del motivo por el que una sesion no tiene partidos (BE #361).

Va en claves y no en frases —`reason`, `missing`, `tee_color`—: la pantalla
las pone en su idioma (BE #360). El nombre si va hecho: es el de la persona.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.modules.competition.domain.value_objects.match_generation_block import (
    MatchGenerationBlock,
)


class BlockedPlayerDTO(BaseModel):
    """A quien le falta que."""

    user_id: UUID = Field(..., description="El jugador.")
    name: str = Field(..., description="Su nombre en esta competición.")
    missing: str = Field(
        ...,
        description=(
            "Lo que le falta: GENDER (su género), TEE_COLOR (su color en el campo) o "
            "ENROLLMENT (la inscripción aprobada)."
        ),
    )
    tee_color: str | None = Field(
        None, description="El color que se le asignó, si lo que falta es ese color en el campo."
    )


class MatchGenerationBlockDTO(BaseModel):
    """Por qué no se pudieron generar los partidos al abrir los sobres."""

    reason: str = Field(
        ...,
        description=(
            "PLAYERS_WITHOUT_TEE, NOT_ENOUGH_PLAYERS, NO_TEAMS, NO_GOLF_COURSE, "
            "ENROLLMENT_OPEN o UNEXPECTED."
        ),
    )
    players: list[BlockedPlayerDTO] = Field(
        default_factory=list, description="Los jugadores afectados, cuando el motivo es de ellos."
    )
    at: datetime | None = Field(None, description="Cuándo se intentó.")


def block_to_dto(block: MatchGenerationBlock | None) -> MatchGenerationBlockDTO | None:
    """Del valor de dominio al DTO, o None si no hay motivo."""
    if block is None:
        return None
    return MatchGenerationBlockDTO(
        reason=block.reason,
        players=[
            BlockedPlayerDTO(
                user_id=p.user_id.value, name=p.name, missing=p.missing, tee_color=p.tee_color
            )
            for p in block.players
        ],
        at=block.at,
    )


class SessionWithoutMatchesDTO(BaseModel):
    """Una sesion con los sobres abiertos y sin partidos, para el organizador."""

    round_id: UUID = Field(..., description="La sesión.")
    competition_id: UUID = Field(..., description="Su competición.")
    competition_name: str = Field(..., description="Para pintarla sin pedirla aparte.")
    round_date: date = Field(..., description="Qué día se juega.")
    session_type: str = Field(..., description="Mañana, tarde o noche.")
    reason: str = Field(..., description="El motivo, como en MatchGenerationBlockDTO.")
    players: list[BlockedPlayerDTO] = Field(
        default_factory=list, description="A quién le falta qué."
    )
