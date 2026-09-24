"""Tests para CompetitionStatus Value Object - transiciones de estado."""

import pytest

from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)


class TestCompetitionStatusForwardTransitions:
    """Tests para transiciones forward del ciclo de vida."""

    def test_draft_can_transition_to_active(self):
        """DRAFT → ACTIVE es válido."""
        assert CompetitionStatus.DRAFT.can_transition_to(CompetitionStatus.ACTIVE) is True

    def test_active_can_transition_to_closed(self):
        """ACTIVE → CLOSED es válido."""
        assert CompetitionStatus.ACTIVE.can_transition_to(CompetitionStatus.CLOSED) is True

    def test_closed_can_transition_to_in_progress(self):
        """CLOSED → IN_PROGRESS es válido."""
        assert CompetitionStatus.CLOSED.can_transition_to(CompetitionStatus.IN_PROGRESS) is True

    def test_in_progress_can_transition_to_completed(self):
        """IN_PROGRESS → COMPLETED es válido."""
        assert CompetitionStatus.IN_PROGRESS.can_transition_to(CompetitionStatus.COMPLETED) is True

    def test_any_non_final_can_transition_to_cancelled(self):
        """Cualquier estado no final puede ir a CANCELLED."""
        assert CompetitionStatus.DRAFT.can_transition_to(CompetitionStatus.CANCELLED) is True
        assert CompetitionStatus.ACTIVE.can_transition_to(CompetitionStatus.CANCELLED) is True
        assert CompetitionStatus.CLOSED.can_transition_to(CompetitionStatus.CANCELLED) is True
        assert CompetitionStatus.IN_PROGRESS.can_transition_to(CompetitionStatus.CANCELLED) is True


class TestCompetitionStatusBackwardTransitions:
    """Tests para transiciones backward (nueva funcionalidad)."""

    def test_in_progress_can_transition_to_closed(self):
        """IN_PROGRESS → CLOSED es válido (revertir para corregir schedule)."""
        assert CompetitionStatus.IN_PROGRESS.can_transition_to(CompetitionStatus.CLOSED) is True

    def test_closed_can_transition_to_active(self):
        """CLOSED → ACTIVE es válido (reabrir inscripciones)."""
        assert CompetitionStatus.CLOSED.can_transition_to(CompetitionStatus.ACTIVE) is True


class TestCompetitionStatusInvalidTransitions:
    """Tests para transiciones inválidas."""

    def test_completed_cannot_transition_to_closed(self):
        """COMPLETED → CLOSED es inválido (estado terminal)."""
        assert CompetitionStatus.COMPLETED.can_transition_to(CompetitionStatus.CLOSED) is False

    def test_cancelled_cannot_transition_to_anything(self):
        """CANCELLED no puede transicionar a ningún estado (estado terminal)."""
        for target in CompetitionStatus:
            assert CompetitionStatus.CANCELLED.can_transition_to(target) is False

    def test_completed_cannot_transition_to_anything(self):
        """COMPLETED no puede transicionar a ningún estado (estado terminal)."""
        for target in CompetitionStatus:
            assert CompetitionStatus.COMPLETED.can_transition_to(target) is False

    def test_draft_cannot_skip_to_closed(self):
        """DRAFT → CLOSED es inválido (no se puede saltar ACTIVE)."""
        assert CompetitionStatus.DRAFT.can_transition_to(CompetitionStatus.CLOSED) is False

    def test_draft_cannot_skip_to_in_progress(self):
        """DRAFT → IN_PROGRESS es inválido (no se puede saltar)."""
        assert CompetitionStatus.DRAFT.can_transition_to(CompetitionStatus.IN_PROGRESS) is False

    def test_active_cannot_skip_to_in_progress(self):
        """ACTIVE → IN_PROGRESS es inválido (no se puede saltar CLOSED)."""
        assert CompetitionStatus.ACTIVE.can_transition_to(CompetitionStatus.IN_PROGRESS) is False

    def test_active_cannot_revert_to_draft(self):
        """ACTIVE → DRAFT es inválido (sin backward a DRAFT)."""
        assert CompetitionStatus.ACTIVE.can_transition_to(CompetitionStatus.DRAFT) is False


class TestCompetitionStatusHelpers:
    """Tests para métodos auxiliares."""

    def test_is_active_returns_true_for_active(self):
        """is_active() es True solo para ACTIVE."""
        assert CompetitionStatus.ACTIVE.is_active() is True
        assert CompetitionStatus.DRAFT.is_active() is False

    def test_is_final_returns_true_for_terminal_states(self):
        """is_final() es True para COMPLETED y CANCELLED."""
        assert CompetitionStatus.COMPLETED.is_final() is True
        assert CompetitionStatus.CANCELLED.is_final() is True
        assert CompetitionStatus.DRAFT.is_final() is False
        assert CompetitionStatus.IN_PROGRESS.is_final() is False

    def test_allows_modifications_while_enrollment_is_open(self):
        """BE #323: se puede corregir el montaje mientras hay inscripciones abiertas.

        Antes solo DRAFT. Con la invitacion abriendo el torneo (BE #319), dejarlo
        ahi convertia invitar en una puerta de un solo sentido: sin campo de golf
        puesto, el torneo ya no se podia jugar nunca.
        """
        assert CompetitionStatus.DRAFT.allows_modifications() is True
        assert CompetitionStatus.ACTIVE.allows_modifications() is True

    def test_does_not_allow_modifications_once_enrollment_closes(self):
        """De CLOSED en adelante se sortean equipos y se generan partidos."""
        assert CompetitionStatus.CLOSED.allows_modifications() is False
        assert CompetitionStatus.IN_PROGRESS.allows_modifications() is False
        assert CompetitionStatus.COMPLETED.allows_modifications() is False
        assert CompetitionStatus.CANCELLED.allows_modifications() is False

    @pytest.mark.parametrize(
        ("status", "esperado"),
        [
            (CompetitionStatus.DRAFT, True),
            (CompetitionStatus.ACTIVE, True),
            (CompetitionStatus.CLOSED, True),
            (CompetitionStatus.IN_PROGRESS, True),
            (CompetitionStatus.COMPLETED, False),
            (CompetitionStatus.CANCELLED, False),
        ],
    )
    def test_golf_courses_can_be_added_until_the_competition_is_over(self, status, esperado):
        """BE #368: anadir un campo no toca ninguna sesion, asi que no espera a nada."""
        assert status.allows_adding_golf_courses() is esperado

    def test_allows_deletion_while_enrollment_is_open(self):
        """BE #333: un torneo recien creado se puede borrar, abierto o no.

        Con las competiciones naciendo con las inscripciones abiertas (BE #332),
        dejar el borrado solo en DRAFT significaria que equivocarse al crearlas
        ya no se deshace: solo quedaria cancelarlas, y la cancelada se queda en
        la lista para siempre.
        """
        assert CompetitionStatus.DRAFT.allows_deletion() is True
        assert CompetitionStatus.ACTIVE.allows_deletion() is True

    def test_allows_deletion_of_a_cancelled_competition(self):
        """Una cancelada tambien se borra: cancelar era la salida, no el destino.

        El motivo de todo esto es que equivocarse al crear un torneo no deje una
        fila muerta para siempre, y dejar CANCELLED fuera reproducia justo eso.
        Lo que protege al historial de verdad no es el estado, sino no tener
        nada jugado, que el caso de uso comprueba aparte.
        """
        assert CompetitionStatus.CANCELLED.allows_deletion() is True

    def test_allows_deletion_of_a_closed_competition(self):
        """BE #347: cerrar las inscripciones no hace sagrado el torneo.

        En CLOSED se sortean equipos y se monta el calendario, y todo eso se
        rehace. Lo irrecuperable son los golpes, y de eso se encarga la otra
        mitad de la regla, que mira lo jugado y no el estado.
        """
        assert CompetitionStatus.CLOSED.allows_deletion() is True

    def test_does_not_allow_deletion_while_being_played_or_once_finished(self):
        """En juego o terminado, nunca: ahi el torneo ES lo jugado."""
        assert CompetitionStatus.IN_PROGRESS.allows_deletion() is False
        assert CompetitionStatus.COMPLETED.allows_deletion() is False
