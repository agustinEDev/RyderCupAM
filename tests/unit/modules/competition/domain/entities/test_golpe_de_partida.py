"""
El golpe de un jugador en un hoyo de su partida de stroke play (#251, PR 5).

Lo apunta él (o el organizador, decisión 11) y lo apunta su marcador; vale
cuando coinciden. Medal no deja levantar bola; Stableford sí (vale 0 puntos).

| Caso                                              | Resultado               |
|---------------------------------------------------|-------------------------|
| Hoyo 0 o 19 / golpes 0 o 16                       | Error                   |
| Nuevo, o solo un lado                             | PENDING                 |
| Los dos iguales / distintos                       | MATCH / MISMATCH        |
| Raya en los dos, Stableford                       | MATCH, sin golpes       |
| Raya en Medal, en cualquier lado                  | RayaNoPermitidaError    |
| Corregir un lado validado a otro valor            | MISMATCH                |
| Quién metió cada lado                             | Queda guardado          |
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.golpe_de_partida import (
    GolpeDePartida,
    RayaNoPermitidaError,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.validation_status import ValidationStatus
from src.modules.user.domain.value_objects.user_id import UserId

AHORA = datetime(2030, 10, 11, 9, 0, tzinfo=UTC)
JUGADOR, MARCADOR = UserId.generate(), UserId.generate()


def _golpe(hoyo: int = 1) -> GolpeDePartida:
    return GolpeDePartida.crear(
        partida_id=PartidaId.generate(),
        round_id=RoundId.generate(),
        competition_id=CompetitionId(uuid4()),
        user_id=JUGADOR,
        hoyo=hoyo,
        momento=AHORA,
    )


@pytest.mark.parametrize("hoyo", [0, 19])
def test_a_hole_out_of_the_card(hoyo):
    with pytest.raises(ValueError):
        _golpe(hoyo)


@pytest.mark.parametrize("golpes", [0, 16])
def test_strokes_out_of_range(golpes):
    with pytest.raises(ValueError):
        _golpe().anotar_propio(golpes, acepta_raya=True, quien=JUGADOR, momento=AHORA)


def test_new_or_one_side_only_is_pending():
    golpe = _golpe()
    assert golpe.estado == ValidationStatus.PENDING

    golpe.anotar_propio(4, acepta_raya=False, quien=JUGADOR, momento=AHORA)

    assert golpe.estado == ValidationStatus.PENDING
    assert not golpe.validado


@pytest.mark.parametrize(
    ("propio", "del_marcador", "estado"),
    [(4, 4, ValidationStatus.MATCH), (4, 5, ValidationStatus.MISMATCH)],
)
def test_both_sides(propio, del_marcador, estado):
    golpe = _golpe()

    golpe.anotar_propio(propio, acepta_raya=False, quien=JUGADOR, momento=AHORA)
    golpe.anotar_del_marcador(del_marcador, acepta_raya=False, quien=MARCADOR, momento=AHORA)

    assert golpe.estado == estado
    assert golpe.validado == (estado == ValidationStatus.MATCH)


def test_a_picked_up_ball_in_stableford_validates_without_strokes():
    golpe = _golpe()

    golpe.anotar_propio(None, acepta_raya=True, quien=JUGADOR, momento=AHORA)
    golpe.anotar_del_marcador(None, acepta_raya=True, quien=MARCADOR, momento=AHORA)

    assert golpe.validado
    assert golpe.golpes_validados is None


@pytest.mark.parametrize("lado", ["anotar_propio", "anotar_del_marcador"])
def test_no_picked_up_ball_in_medal(lado):
    with pytest.raises(RayaNoPermitidaError):
        getattr(_golpe(), lado)(None, acepta_raya=False, quien=JUGADOR, momento=AHORA)


def test_correcting_a_validated_side_unvalidates_it():
    golpe = _golpe()
    golpe.anotar_propio(4, acepta_raya=False, quien=JUGADOR, momento=AHORA)
    golpe.anotar_del_marcador(4, acepta_raya=False, quien=MARCADOR, momento=AHORA)

    golpe.anotar_del_marcador(5, acepta_raya=False, quien=MARCADOR, momento=AHORA)

    assert golpe.estado == ValidationStatus.MISMATCH
    assert golpe.golpes_validados is None


def test_who_entered_each_side_is_kept():
    organizador = UserId.generate()
    golpe = _golpe()

    golpe.anotar_propio(4, acepta_raya=False, quien=organizador, momento=AHORA)
    golpe.anotar_del_marcador(4, acepta_raya=False, quien=MARCADOR, momento=AHORA)

    assert (golpe.propio_por, golpe.marcador_por) == (organizador, MARCADOR)
    assert golpe.golpes_validados == 4
