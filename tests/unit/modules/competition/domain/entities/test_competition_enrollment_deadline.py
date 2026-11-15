"""
El cierre de inscripciones por plazo, en la entidad (15 nov 2026).

| Caso | Regla                                                                       |
|------|-----------------------------------------------------------------------------|
| C1   | El plazo de la competición: 12:00 del día anterior, hora del campo           |
| C2   | Pasado el plazo nadie entra aunque siga ACTIVE                               |
| C2   | En borrador no: quien la abra la abre tarde (R2); cerrada o en juego, sí     |
| C3   | Le toca cerrarse sola: ACTIVE, pasado el plazo y abierta antes de él         |
| C3   | Cerrada por el plazo queda apuntado; cerrada a mano, no                      |
| C4   | El aviso de «no se puede cerrar» se apunta, y se olvida al cerrar o al mover |
| R1   | Reabierta después del plazo: entra gente y no le toca cerrarse sola          |
| R2   | Creada o abierta después del plazo: igual que R1                             |
| R3   | Mover el torneo más tarde: el plazo nuevo manda, y R1 deja de valer          |
| A1   | La apertura programada, de 2 a 14 días                                       |
"""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.play_mode import PlayMode

MADRID = "Europe/Madrid"
TORNEO = date(2026, 11, 20)
# Las 12:00 de Madrid del 19 de noviembre son las 11:00 UTC
PLAZO = datetime(2026, 11, 19, 11, 0, tzinfo=UTC)
ANTES = PLAZO - timedelta(days=3)
DESPUES = PLAZO + timedelta(hours=1)


def _crear(dias: int | None = None, inicio: date = TORNEO) -> Competition:
    return Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=UserId(uuid4()),
        name=CompetitionName("Copa del plazo"),
        dates=DateRange(inicio, inicio + timedelta(days=1)),
        location=Location(main_country="ES"),
        team_1_name="Europa",
        team_2_name="USA",
        play_mode=PlayMode.SCRATCH,
        enrollment_opens_days_before=dias,
    )


def _abierta(cuando: datetime = ANTES, inicio: date = TORNEO) -> Competition:
    competition = _crear(inicio=inicio)
    competition.activate(now=cuando)
    return competition


class TestElPlazo:
    def test_es_el_de_la_politica_con_su_zona(self):
        """C1. Given el torneo del 20 en Madrid / Then cierra el 19 a las 11:00 UTC."""
        assert _abierta().enrollment_deadline(MADRID) == PLAZO

    def test_sin_campo_es_madrid(self):
        """C1. Given sin zona / Then el plazo de Madrid."""
        assert _abierta().enrollment_deadline(None) == PLAZO


class TestNadieEntraPasadoElPlazo:
    def test_antes_del_plazo_se_entra(self):
        """C2. Given abierta antes del plazo / When antes del plazo / Then se entra."""
        assert _abierta().entries_closed_by_deadline(MADRID, PLAZO - timedelta(seconds=1)) is False

    def test_justo_en_el_plazo_ya_no(self):
        """C2. Given abierta antes del plazo / When a las 12:00 en punto / Then ya no se entra."""
        assert _abierta().entries_closed_by_deadline(MADRID, PLAZO) is True

    def test_despues_del_plazo_tampoco_aunque_siga_activa(self):
        """C2. Given ACTIVE abierta antes / When pasado el plazo / Then no se entra."""
        competition = _abierta()

        assert competition.status is CompetitionStatus.ACTIVE
        assert competition.entries_closed_by_deadline(MADRID, DESPUES) is True

    def test_en_borrador_no_lo_impide(self):
        """C2/R2. Given en borrador pasado el plazo / Then no: quien la abra, la abre tarde."""
        assert _crear(dias=5).entries_closed_by_deadline(MADRID, DESPUES) is False

    @pytest.mark.parametrize("hasta", ["CLOSED", "IN_PROGRESS"])
    def test_cerrada_o_en_juego_si(self, hasta):
        """C2. Given cerrada (o en juego) pasado el plazo / Then no entra nadie, ni aprobando."""
        competition = _abierta()
        competition.close_enrollments()
        if hasta == "IN_PROGRESS":
            competition.start()

        assert competition.entries_closed_by_deadline(MADRID, DESPUES) is True

    def test_cerrada_a_mano_tras_reabrirla_tarde_tampoco(self):
        """
        R1/C2. Given reabierta tarde y cerrada otra vez a mano
        Then la excepción de R1 acabó al cerrarla: no entra nadie
        """
        competition = _abierta()
        competition.close_enrollments()
        competition.reopen_enrollments(now=DESPUES)
        competition.close_enrollments()

        assert competition.entries_closed_by_deadline(MADRID, DESPUES) is True

    def test_sin_fecha_de_apertura_guardada_cuenta_como_abierta_antes(self):
        """C2. Given una ACTIVE sin `enrollment_opened_at` (de antes) / Then pasado el plazo, no."""
        competition = _abierta()
        competition._enrollment_opened_at = None

        assert competition.entries_closed_by_deadline(MADRID, DESPUES) is True


class TestLeTocaCerrarse:
    def test_activa_pasado_el_plazo(self):
        """C3. Given ACTIVE abierta antes del plazo / When pasa el plazo / Then le toca."""
        assert _abierta().due_to_close(MADRID, DESPUES) is True

    def test_antes_del_plazo_no(self):
        """C3. Given ACTIVE / When antes del plazo / Then no."""
        assert _abierta().due_to_close(MADRID, PLAZO - timedelta(seconds=1)) is False

    def test_cerrada_no(self):
        """C3. Given ya cerrada / Then no hay nada que cerrar."""
        competition = _abierta()
        competition.close_enrollments()

        assert competition.due_to_close(MADRID, DESPUES) is False

    def test_en_borrador_no(self):
        """C3. Given en borrador / Then el plazo no la toca."""
        assert _crear(dias=5).due_to_close(MADRID, DESPUES) is False


class TestQuienLaCerro:
    def test_por_el_plazo_queda_apuntado(self):
        """C3. Given ACTIVE / When se cierra por el plazo / Then queda dicho."""
        competition = _abierta()

        competition.close_enrollments(total_enrollments=3, by_deadline=True)

        assert competition.status is CompetitionStatus.CLOSED
        assert competition.enrollment_closed_by_deadline is True

    def test_a_mano_no(self):
        """C3. Given ACTIVE / When la cierra el organizador / Then no lo dice."""
        competition = _abierta()

        competition.close_enrollments(total_enrollments=3)

        assert competition.enrollment_closed_by_deadline is False

    def test_reabrir_lo_olvida(self):
        """C3/R1. Given cerrada por el plazo / When se reabre / Then ya no está cerrada por él."""
        competition = _abierta()
        competition.close_enrollments(by_deadline=True)

        competition.reopen_enrollments(now=DESPUES)

        assert competition.enrollment_closed_by_deadline is False

    def test_nombrar_capitanes_es_cerrar_a_mano(self):
        """C3. Given ACTIVE / When se nombran capitanes (cierra) / Then a mano."""
        competition = _abierta()
        a, b = UserId(uuid4()), UserId(uuid4())

        competition.name_captains(a, b, [a, b], has_teams=False)

        assert competition.status is CompetitionStatus.CLOSED
        assert competition.enrollment_closed_by_deadline is False


class TestElAvisoDeQueNoSePuedeCerrar:
    def test_se_apunta(self):
        """C4. Given ACTIVE sin avisar / When se avisa / Then queda apuntado."""
        competition = _abierta()
        assert competition.close_blocked_notified is False

        competition.mark_close_blocked_notified()

        assert competition.close_blocked_notified is True

    def test_al_cerrar_se_olvida(self):
        """C4. Given avisada / When por fin se cierra / Then el apunte se va."""
        competition = _abierta()
        competition.mark_close_blocked_notified()

        competition.close_enrollments(by_deadline=True)

        assert competition.close_blocked_notified is False

    def test_al_mover_el_torneo_se_olvida(self):
        """C4/R3. Given avisada / When se mueven las fechas / Then plazo nuevo, aviso nuevo."""
        competition = _abierta()
        competition.mark_close_blocked_notified()

        competition.update_info(dates=DateRange(TORNEO + timedelta(days=7), TORNEO + timedelta(8)))

        assert competition.close_blocked_notified is False

    def test_cambiar_otra_cosa_no_lo_olvida(self):
        """C4. Given avisada / When solo cambia el nombre / Then sigue apuntado."""
        competition = _abierta()
        competition.mark_close_blocked_notified()

        competition.update_info(name=CompetitionName("Otro nombre"))

        assert competition.close_blocked_notified is True

    def test_con_las_mismas_fechas_tampoco(self):
        """C4. Given avisada / When llegan las mismas fechas / Then sigue apuntado."""
        competition = _abierta()
        competition.mark_close_blocked_notified()

        competition.update_info(dates=DateRange(TORNEO, TORNEO + timedelta(days=1)))

        assert competition.close_blocked_notified is True


class TestReabiertaDespuesDelPlazo:
    def test_entra_gente_y_no_se_cierra_sola(self):
        """
        R1. Given cerrada y reabierta por el organizador después del plazo
        When se pregunta pasado el plazo
        Then se entra, y no le toca cerrarse sola
        """
        competition = _abierta()
        competition.close_enrollments()

        competition.reopen_enrollments(now=DESPUES)

        assert competition.entries_closed_by_deadline(MADRID, DESPUES + timedelta(days=1)) is False
        assert competition.due_to_close(MADRID, DESPUES + timedelta(days=1)) is False

    def test_reabierta_justo_en_el_plazo_cuenta_como_despues(self):
        """R1. Given reabierta a las 12:00 en punto / Then es después del plazo."""
        competition = _abierta()
        competition.close_enrollments()

        competition.reopen_enrollments(now=PLAZO)

        assert competition.due_to_close(MADRID, DESPUES) is False

    def test_reabierta_antes_del_plazo_se_cierra_en_el_plazo(self):
        """R1. Given reabierta ANTES del plazo / When pasa el plazo / Then le toca cerrarse."""
        competition = _abierta()
        competition.close_enrollments()

        competition.reopen_enrollments(now=PLAZO - timedelta(hours=2))

        assert competition.due_to_close(MADRID, DESPUES) is True

    def test_la_apertura_se_guarda_en_utc_sin_zona(self):
        """R1. Given reabierta con un reloj con zona / Then se guarda en UTC sin zona."""
        competition = _abierta()
        competition.close_enrollments()

        competition.reopen_enrollments(now=datetime(2026, 11, 19, 13, 0, tzinfo=UTC))

        assert competition.enrollment_opened_at == datetime(2026, 11, 19, 13, 0)


class TestAbiertaDespuesDelPlazo:
    def test_creada_y_abierta_tarde(self):
        """R2. Given creada y abierta después del plazo / Then se entra y no se cierra sola."""
        competition = _abierta(cuando=DESPUES)

        assert competition.entries_closed_by_deadline(MADRID, DESPUES) is False
        assert competition.due_to_close(MADRID, DESPUES) is False

    def test_sin_reloj_usa_el_de_ahora(self):
        """R2. Given un torneo de ayer abierto sin pasar reloj / Then cuenta como abierta tarde."""
        ayer = datetime.now(UTC).date() - timedelta(days=1)
        competition = _crear(inicio=ayer)

        competition.activate()

        assert competition.due_to_close(MADRID, datetime.now(UTC)) is False

    def test_reabrir_sin_reloj_usa_el_de_ahora(self):
        """R1. Given un torneo de ayer reabierto sin pasar reloj / Then cuenta como tarde."""
        ayer = datetime.now(UTC).date() - timedelta(days=1)
        competition = _abierta(cuando=datetime(2020, 1, 1, tzinfo=UTC), inicio=ayer)
        competition.close_enrollments()

        competition.reopen_enrollments()

        assert competition.due_to_close(MADRID, datetime.now(UTC)) is False


class TestMoverElTorneo:
    def test_mas_tarde_vuelve_a_mandar_el_plazo_nuevo(self):
        """
        R3. Given reabierta después del plazo (R1)
        When el organizador mueve el torneo una semana más tarde
        Then R1 deja de valer: se entra hasta el plazo nuevo y ahí le toca cerrarse
        """
        competition = _abierta()
        competition.close_enrollments()
        competition.reopen_enrollments(now=DESPUES)

        nuevo = TORNEO + timedelta(days=7)
        competition.update_info(dates=DateRange(nuevo, nuevo + timedelta(days=1)))

        nuevo_plazo = PLAZO + timedelta(days=7)
        assert competition.entries_closed_by_deadline(MADRID, nuevo_plazo - timedelta(1)) is False
        assert competition.due_to_close(MADRID, nuevo_plazo) is True


class TestLaAperturaProgramada:
    @pytest.mark.parametrize("dias", [2, 7, 14])
    def test_de_dos_a_catorce(self, dias):
        """A1. Given de 2 a 14 días / Then vale."""
        assert _crear(dias).enrollment_opens_days_before == dias

    @pytest.mark.parametrize("dias", [0, 1, 15])
    def test_uno_ya_no(self, dias):
        """A1. Given 1 día (abriría a las 0:00 y cerraría a las 12:00) / Then no vale."""
        with pytest.raises(ValueError, match="2 y 14"):
            _crear(dias)
