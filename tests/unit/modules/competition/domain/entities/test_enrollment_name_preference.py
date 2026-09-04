"""El nombre con el que una competición muestra a un jugador (BE #254)."""

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.user.domain.value_objects.user_id import UserId


class TestNamePreferenceDefault:
    """
    El valor de partida, que es una decisión de producto y no un detalle de la
    columna: una competición tiene lista de salida y clasificación pública, así
    que enseña el nombre legal mientras nadie pida su alias para ella.
    """

    def test_una_inscripcion_nueva_nace_con_el_nombre_legal(self):
        enrollment = Enrollment.request(
            id=EnrollmentId.generate(),
            competition_id=CompetitionId.generate(),
            user_id=UserId.generate(),
        )

        assert enrollment.use_real_name is True

    def test_la_inscripcion_directa_del_creador_tambien(self):
        enrollment = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=CompetitionId.generate(),
            user_id=UserId.generate(),
        )

        assert enrollment.use_real_name is True

    def test_pedir_el_alias_es_una_eleccion_explicita(self):
        enrollment = Enrollment.request(
            id=EnrollmentId.generate(),
            competition_id=CompetitionId.generate(),
            user_id=UserId.generate(),
        )

        enrollment.set_name_preference(False)

        assert enrollment.use_real_name is False
