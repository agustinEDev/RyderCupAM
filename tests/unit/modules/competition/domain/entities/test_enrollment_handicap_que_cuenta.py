"""El hándicap con el que juega un inscrito en SU competición (RyderCupAM#251).

La misma regla estaba copiada en la generación de partidos, el draft y los
sobres; el stroke play la necesita una vez más para fijar la categoría. Vive en
la inscripción para que no haya una quinta copia.
"""

from decimal import Decimal

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.user.domain.value_objects.user_id import UserId


def _inscripcion(personalizado: Decimal | None = None) -> Enrollment:
    return Enrollment.direct_enroll(
        id=EnrollmentId.generate(),
        competition_id=CompetitionId.generate(),
        user_id=UserId.generate(),
        custom_handicap=personalizado,
    )


class TestHandicapQueCuenta:
    def test_el_personalizado_manda_sobre_el_del_perfil(self):
        assert _inscripcion(Decimal("8.0")).handicap_que_cuenta(Decimal("14.2")) == Decimal("8.0")

    def test_sin_personalizado_cuenta_el_del_perfil(self):
        assert _inscripcion().handicap_que_cuenta(Decimal("14.2")) == Decimal("14.2")

    def test_sin_ninguno_no_hay_handicap(self):
        """Ni cero: el cero es la salida de la Ryder, y el stroke play no la quiere."""
        assert _inscripcion().handicap_que_cuenta(None) is None

    def test_un_personalizado_de_cero_es_un_handicap(self):
        """Un `or` lo tomaría por «no hay» y se iría al del perfil."""
        assert _inscripcion(Decimal("0.0")).handicap_que_cuenta(Decimal("14.2")) == Decimal("0.0")

    def test_un_personalizado_plus_tambien(self):
        assert _inscripcion(Decimal("-2.0")).handicap_que_cuenta(Decimal("3.1")) == Decimal("-2.0")
