"""El hándicap con el que empezó un jugador queda fijado en su inscripción (1c, #251)."""

from decimal import Decimal

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.user.domain.value_objects.user_id import UserId


def _inscripcion() -> Enrollment:
    return Enrollment.direct_enroll(
        id=EnrollmentId.generate(),
        competition_id=CompetitionId.generate(),
        user_id=UserId.generate(),
    )


def test_nace_sin_handicap_congelado():
    assert _inscripcion().fixed_handicap is None


def test_se_congela_el_que_cuenta():
    inscripcion = _inscripcion()

    inscripcion.congelar_handicap(Decimal("14.2"))

    assert inscripcion.fixed_handicap == Decimal("14.2")


def test_al_volver_a_empezar_se_congela_de_nuevo():
    inscripcion = _inscripcion()
    inscripcion.congelar_handicap(Decimal("14.2"))

    inscripcion.congelar_handicap(Decimal("13.8"))

    assert inscripcion.fixed_handicap == Decimal("13.8")


def test_sin_handicap_se_congela_sin_el():
    inscripcion = _inscripcion()
    inscripcion.congelar_handicap(Decimal("14.2"))

    inscripcion.congelar_handicap(None)

    assert inscripcion.fixed_handicap is None
