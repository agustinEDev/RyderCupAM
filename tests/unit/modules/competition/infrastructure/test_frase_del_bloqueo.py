"""
La frase del 400 de «Generar» cuando la sesión queda bloqueada (BE #360).

Lo que cuenta es el motivo en claves; esta frase es para el cliente que aún no
las lee. Se compone en la ruta a partir del motivo, no con el mensaje de la
excepción (CodeQL: información de una excepción expuesta al usuario).
"""

from src.modules.competition.domain.value_objects.match_generation_block import (
    NOT_ENOUGH_PLAYERS,
    PLAYERS_WITHOUT_TEE,
    BlockedPlayer,
    MatchGenerationBlock,
)
from src.modules.competition.infrastructure.api.v1.round_match_routes import frase_del_bloqueo
from src.modules.user.domain.value_objects.user_id import UserId


def test_con_jugadores_los_nombra():
    motivo = MatchGenerationBlock(
        reason=PLAYERS_WITHOUT_TEE,
        players=(
            BlockedPlayer(user_id=UserId.generate(), name="Eva Esteban", missing="GENDER"),
            BlockedPlayer(user_id=UserId.generate(), name="", missing="TEE_COLOR"),
        ),
    )

    assert frase_del_bloqueo(motivo) == (
        "No se pueden generar los partidos: faltan datos de Eva Esteban, un jugador"
    )


def test_sin_jugadores_remite_a_la_sesion():
    assert frase_del_bloqueo(MatchGenerationBlock(reason=NOT_ENOUGH_PLAYERS)) == (
        "No se pueden generar los partidos: el motivo está en la sesión"
    )
