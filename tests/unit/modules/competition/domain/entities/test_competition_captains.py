"""Los capitanes de la competicion (BE #320).

Decidido el 20 sep: nadie quiere pulsar «cerrar inscripciones», pero nombrar a
los capitanes si es algo que el organizador quiere hacer, y es lo que de verdad
congela la plantilla. Nombrarlos cierra las inscripciones.

Y el 22 sep: se guardan en la competicion, uno por equipo; se pueden cambiar
mientras no haya equipos repartidos; y si uno se da de baja, su puesto queda
libre.
"""

from datetime import date

import pytest

from src.modules.competition.domain.entities.competition import (
    CaptainMissingError,
    CaptainNotEnrolledError,
    CaptainOnWrongTeamError,
    CaptainsLockedError,
    Competition,
    CompetitionStateError,
    TeamsNotAssignedError,
)
from src.modules.competition.domain.events.competition_enrollments_closed_event import (
    CompetitionEnrollmentsClosedEvent,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

ANA = UserId.generate()
BEA = UserId.generate()
CARLA = UserId.generate()
# Los inscritos aprobados: Ana, Bea, Carla y nueve más
INSCRITOS = [ANA, BEA, CARLA] + [UserId.generate() for _ in range(9)]


def _competicion(estado: CompetitionStatus) -> Competition:
    """Una competición en ese estado, sin eventos pendientes."""
    competicion = Competition(
        id=CompetitionId.generate(),
        creator_id=UserId.generate(),
        name=CompetitionName("Ryder Cup Madrid 2027"),
        dates=DateRange(date(2027, 6, 1), date(2027, 6, 3)),
        location=Location(CountryCode("ES")),
        team_1_name="Europe",
        team_2_name="USA",
        play_mode=PlayMode.HANDICAP,
        status=estado,
    )
    competicion.clear_domain_events()
    return competicion


def _cierres(competicion: Competition) -> list:
    """Los eventos de cierre de inscripciones que tiene pendientes."""
    return [
        e
        for e in competicion.get_domain_events()
        if isinstance(e, CompetitionEnrollmentsClosedEvent)
    ]


class TestNameCaptains:
    def test_con_las_inscripciones_abiertas_nombrarlos_las_cierra(self):
        """Es la accion con proposito que sustituye a «cerrar inscripciones»."""
        competicion = _competicion(CompetitionStatus.ACTIVE)

        competicion.name_captains(ANA, BEA, approved_player_ids=INSCRITOS, has_teams=False)

        assert competicion.team_a_captain_id == ANA
        assert competicion.team_b_captain_id == BEA
        assert competicion.status == CompetitionStatus.CLOSED
        # El mismo evento que cerrar a mano: quien escuche el cierre, se entera
        assert [e.total_enrollments for e in _cierres(competicion)] == [12]

    def test_ya_cerrada_se_pueden_cambiar_sin_volver_a_cerrar(self):
        """
        Given: capitanes nombrados, que la cerraron
        When: se cambia la capitana del A
        Then: cambia, sigue CLOSED y no sale un segundo evento de cierre
        """
        competicion = _competicion(CompetitionStatus.ACTIVE)
        competicion.name_captains(ANA, BEA, approved_player_ids=INSCRITOS, has_teams=False)
        competicion.clear_domain_events()

        competicion.name_captains(CARLA, BEA, approved_player_ids=INSCRITOS, has_teams=False)

        assert competicion.team_a_captain_id == CARLA
        assert competicion.status == CompetitionStatus.CLOSED
        assert _cierres(competicion) == []

    @pytest.mark.parametrize("estado", [CompetitionStatus.ACTIVE, CompetitionStatus.CLOSED])
    def test_con_los_equipos_repartidos_ya_no_se_cambian(self, estado):
        """Cambiar un capitan despues exigiria rehacer los equipos.

        En ACTIVE tambien: reabrir las inscripciones no deshace el reparto.
        """
        competicion = _competicion(estado)

        with pytest.raises(CaptainsLockedError):
            competicion.name_captains(ANA, BEA, approved_player_ids=INSCRITOS, has_teams=True)

        assert competicion.team_a_captain_id is None
        assert competicion.status == estado

    @pytest.mark.parametrize(
        "estado",
        [
            CompetitionStatus.DRAFT,
            CompetitionStatus.IN_PROGRESS,
            CompetitionStatus.COMPLETED,
            CompetitionStatus.CANCELLED,
        ],
    )
    def test_fuera_de_la_preparacion_no_se_nombran(self, estado):
        """En borrador nadie se ha inscrito todavia; despues, el torneo ya va."""
        competicion = _competicion(estado)

        with pytest.raises(CompetitionStateError):
            competicion.name_captains(ANA, BEA, approved_player_ids=INSCRITOS, has_teams=False)

        assert competicion.team_a_captain_id is None
        assert competicion.status == estado

    def test_la_misma_persona_no_capitanea_los_dos_equipos(self):
        """
        Given: una abierta
        When: se nombra a Ana para los dos equipos
        Then: se rechaza y no cambia nada
        """
        competicion = _competicion(CompetitionStatus.ACTIVE)

        with pytest.raises(ValueError, match="distint"):
            competicion.name_captains(ANA, ANA, approved_player_ids=INSCRITOS, has_teams=False)

        assert competicion.team_a_captain_id is None
        assert competicion.status == CompetitionStatus.ACTIVE

    @pytest.mark.parametrize("cual", ["A", "B"])
    def test_un_capitan_tiene_que_ser_un_inscrito_aprobado(self, cual):
        """Los capitanes siempre juegan: dos de los inscritos, no dos personas mas."""
        competicion = _competicion(CompetitionStatus.ACTIVE)
        ajeno = UserId.generate()
        a, b = (ajeno, BEA) if cual == "A" else (ANA, ajeno)

        with pytest.raises(CaptainNotEnrolledError):
            competicion.name_captains(a, b, approved_player_ids=INSCRITOS, has_teams=False)

        assert competicion.team_a_captain_id is None
        assert competicion.status == CompetitionStatus.ACTIVE

    def test_nace_sin_capitanes(self):
        """
        Given: una competición recién creada
        When: se miran sus capitanes
        Then: no tiene ninguno
        """
        competicion = _competicion(CompetitionStatus.ACTIVE)

        assert competicion.team_a_captain_id is None
        assert competicion.team_b_captain_id is None


class TestHandleWithdrawalBeforeTheDraft:
    def _con_capitanes(self) -> Competition:
        """Abierta con Ana y Bea de capitanas, lo que la deja cerrada."""
        competicion = _competicion(CompetitionStatus.ACTIVE)
        competicion.name_captains(ANA, BEA, approved_player_ids=INSCRITOS, has_teams=False)
        return competicion

    def test_libera_el_puesto_del_capitan_a(self):
        """
        Given: Ana y Bea capitanas, sin equipos
        When: Ana se da de baja
        Then: su puesto queda libre y Bea sigue
        """
        competicion = self._con_capitanes()

        assert competicion.handle_withdrawal(ANA) is True

        assert competicion.team_a_captain_id is None
        assert competicion.team_b_captain_id == BEA

    def test_libera_el_puesto_del_capitan_b(self):
        """
        Given: Ana y Bea capitanas, sin equipos
        When: Bea se da de baja
        Then: su puesto queda libre y Ana sigue
        """
        competicion = self._con_capitanes()

        assert competicion.handle_withdrawal(BEA) is True

        assert competicion.team_a_captain_id == ANA
        assert competicion.team_b_captain_id is None

    def test_quien_no_es_capitan_no_cambia_nada(self):
        """
        Given: Ana y Bea capitanas
        When: Carla se da de baja
        Then: nada cambia y se dice que no era capitana
        """
        competicion = self._con_capitanes()

        assert competicion.handle_withdrawal(CARLA) is False

        assert (competicion.team_a_captain_id, competicion.team_b_captain_id) == (ANA, BEA)


class TestCaptainsForTeamSplit:
    """Qué capitanes cuentan al repartir equipos: los dos, ninguno, o falta uno."""

    def test_sin_capitanes_no_hay_nadie_fijo(self):
        """El flujo viejo convive durante la transición: reparte a todos."""
        assert _competicion(CompetitionStatus.CLOSED).captains_for_team_split() is None

    def test_con_los_dos_devuelve_la_pareja(self):
        """
        Given: los dos capitanes nombrados
        When: se piden para repartir
        Then: vienen los dos, en su orden
        """
        competicion = _competicion(CompetitionStatus.ACTIVE)
        competicion.name_captains(ANA, BEA, approved_player_ids=INSCRITOS, has_teams=False)

        assert competicion.captains_for_team_split() == (ANA, BEA)

    @pytest.mark.parametrize("se_va", ["A", "B"])
    def test_con_uno_solo_no_se_reparte_cojo(self, se_va):
        """
        Given: un capitán se ha ido
        When: se piden para repartir
        Then: se rechaza pidiendo el que falta
        """
        competicion = _competicion(CompetitionStatus.ACTIVE)
        competicion.name_captains(ANA, BEA, approved_player_ids=INSCRITOS, has_teams=False)
        competicion.handle_withdrawal(ANA if se_va == "A" else BEA)

        with pytest.raises(CaptainMissingError):
            competicion.captains_for_team_split()


class TestCheckCaptainsPlacement:
    """En el reparto manual, cada capitán tiene que estar en el equipo que capitanea."""

    def _con_capitanes(self) -> Competition:
        """Abierta con Ana y Bea de capitanas, lo que la deja cerrada."""
        competicion = _competicion(CompetitionStatus.ACTIVE)
        competicion.name_captains(ANA, BEA, approved_player_ids=INSCRITOS, has_teams=False)
        return competicion

    def test_cada_uno_en_el_suyo_vale(self):
        """
        Given: capitanes nombrados
        When: cada uno aparece en su equipo
        Then: se acepta
        """
        self._con_capitanes().check_captains_placement([ANA, CARLA], [BEA])

    @pytest.mark.parametrize(
        ("equipo_a", "equipo_b"),
        [([BEA, CARLA], [ANA]), ([ANA, BEA], [CARLA]), ([CARLA], [BEA])],
        ids=["cambiados", "B en el A", "A fuera"],
    )
    def test_un_capitan_fuera_de_su_equipo(self, equipo_a, equipo_b):
        """
        Given: capitanes nombrados
        When: están cambiados, juntos o uno fuera
        Then: se rechaza
        """
        with pytest.raises(CaptainOnWrongTeamError):
            self._con_capitanes().check_captains_placement(equipo_a, equipo_b)

    def test_sin_capitanes_no_se_comprueba_nada(self):
        """
        Given: una competición sin capitanes
        When: se comprueba cualquier reparto
        Then: se acepta: es el flujo de antes
        """
        _competicion(CompetitionStatus.CLOSED).check_captains_placement([BEA], [ANA])

    def test_con_uno_solo_tampoco_se_acepta(self):
        """
        Given: un capitán se ha ido
        When: se comprueba el reparto
        Then: se rechaza pidiendo el que falta
        """
        competicion = self._con_capitanes()
        competicion.handle_withdrawal(BEA)

        with pytest.raises(CaptainMissingError):
            competicion.check_captains_placement([ANA], [CARLA])


# ======================================================================================
# Subcapitanes (decidido el 22 sep): cada capitán elige al suyo tras el draft, y
# asciende si el capitán se va. El organizador cubre un puesto de capitán vacío.
# ======================================================================================

DANI = UserId.generate()
EVA = UserId.generate()
# El reparto: Ana capitanea el A con Carla y Dani; Bea el B con Eva
EQUIPO_A = [ANA, CARLA, DANI]
EQUIPO_B = [BEA, EVA]


def _repartida(estado: CompetitionStatus = CompetitionStatus.CLOSED) -> Competition:
    """Con Ana y Bea de capitanas (lo que la deja CLOSED), y el torneo en `estado`."""
    competicion = _competicion(CompetitionStatus.ACTIVE)
    competicion.name_captains(
        ANA, BEA, approved_player_ids=[*INSCRITOS, DANI, EVA], has_teams=False
    )
    if estado in (CompetitionStatus.IN_PROGRESS, CompetitionStatus.COMPLETED):
        competicion.start()
    if estado == CompetitionStatus.COMPLETED:
        competicion.complete()
    return competicion


class TestNameViceCaptain:
    def test_tras_el_draft_se_elige_entre_los_del_equipo(self):
        """
        Given: equipos repartidos
        When: cada capitana elige a uno de su equipo
        Then: quedan los dos subcapitanes
        """
        competicion = _repartida()

        competicion.name_vice_captain("A", CARLA, team_player_ids=EQUIPO_A, has_teams=True)
        competicion.name_vice_captain("B", EVA, team_player_ids=EQUIPO_B, has_teams=True)

        assert competicion.team_a_vice_captain_id == CARLA
        assert competicion.team_b_vice_captain_id == EVA

    def test_elegir_otro_sustituye_al_anterior(self):
        """
        Given: Carla de subcapitana del A
        When: se elige a Dani
        Then: Dani sustituye a Carla
        """
        competicion = _repartida()
        competicion.name_vice_captain("A", CARLA, team_player_ids=EQUIPO_A, has_teams=True)

        competicion.name_vice_captain("A", DANI, team_player_ids=EQUIPO_A, has_teams=True)

        assert competicion.team_a_vice_captain_id == DANI

    def test_antes_del_draft_no_hay_equipo_del_que_elegir(self):
        """
        Given: capitanes nombrados sin equipos
        When: se elige subcapitán
        Then: se rechaza
        """
        competicion = _repartida()

        with pytest.raises(TeamsNotAssignedError):
            competicion.name_vice_captain("A", CARLA, team_player_ids=EQUIPO_A, has_teams=False)

    def test_tiene_que_ser_de_su_equipo(self):
        """
        Given: equipos repartidos
        When: se elige a alguien de fuera de ese equipo
        Then: se rechaza y no queda ninguno
        """
        competicion = _repartida()

        with pytest.raises(CaptainOnWrongTeamError):
            competicion.name_vice_captain("A", EVA, team_player_ids=EQUIPO_A, has_teams=True)

        assert competicion.team_a_vice_captain_id is None

    def test_el_capitan_no_es_su_propio_subcapitan(self):
        """
        Given: equipos repartidos
        When: Ana se elige a sí misma
        Then: se rechaza
        """
        competicion = _repartida()

        with pytest.raises(ValueError, match="capit"):
            competicion.name_vice_captain("A", ANA, team_player_ids=EQUIPO_A, has_teams=True)

    @pytest.mark.parametrize("estado", [CompetitionStatus.IN_PROGRESS, CompetitionStatus.COMPLETED])
    def test_con_el_torneo_en_marcha_no(self, estado):
        """
        Given: el torneo en marcha
        When: se intenta el cambio
        Then: se rechaza por el estado
        """
        competicion = _repartida(estado)

        with pytest.raises(CompetitionStateError):
            competicion.name_vice_captain("A", CARLA, team_player_ids=EQUIPO_A, has_teams=True)

    def test_un_equipo_que_no_existe(self):
        """
        Given: equipos repartidos
        When: se pide el equipo C
        Then: se rechaza
        """
        with pytest.raises(ValueError, match="equipo"):
            _repartida().name_vice_captain("C", CARLA, team_player_ids=EQUIPO_A, has_teams=True)


class TestFillCaptain:
    """El organizador cubre el puesto de un capitán que se fue sin subcapitán."""

    def _sin_capitan_a(self) -> Competition:
        """Repartida, y Ana se ha ido sin subcapitán."""
        competicion = _repartida()
        competicion.handle_withdrawal(ANA)
        return competicion

    def test_cubre_el_puesto_vacio_con_alguien_del_equipo(self):
        """
        Given: Ana se fue sin subcapitán
        When: el organizador pone a Dani
        Then: Dani queda de capitán
        """
        competicion = self._sin_capitan_a()

        competicion.fill_captain("A", DANI, team_player_ids=EQUIPO_A, has_teams=True)

        assert competicion.team_a_captain_id == DANI

    def test_si_era_el_subcapitan_deja_de_serlo(self):
        """Sin capitán, el organizador puede nombrar subcapitán y luego ascenderlo."""
        competicion = self._sin_capitan_a()
        competicion.name_vice_captain("A", DANI, team_player_ids=EQUIPO_A, has_teams=True)

        competicion.fill_captain("A", DANI, team_player_ids=EQUIPO_A, has_teams=True)

        assert (competicion.team_a_captain_id, competicion.team_a_vice_captain_id) == (DANI, None)

    def test_sustituye_a_un_capitan_que_ya_no_sigue_inscrito(self):
        """Se retiró con el torneo en marcha (entonces no se toca nada) y volvió a CLOSED."""
        competicion = _repartida()
        sin_ana = [CARLA, DANI]  # la plantilla del equipo A, ya sin Ana

        competicion.fill_captain("A", DANI, team_player_ids=sin_ana, has_teams=True)

        assert competicion.team_a_captain_id == DANI

    def test_no_sirve_para_cambiar_a_un_capitan_que_sigue(self):
        """
        Given: Ana sigue en el torneo
        When: se intenta cubrir su puesto
        Then: se rechaza y Ana sigue
        """
        competicion = _repartida()

        with pytest.raises(CaptainsLockedError):
            competicion.fill_captain("A", DANI, team_player_ids=EQUIPO_A, has_teams=True)

        assert competicion.team_a_captain_id == ANA

    def test_antes_del_draft_se_nombran_los_dos(self):
        """
        Given: Ana se fue antes del reparto
        When: se intenta cubrir su puesto
        Then: se rechaza: antes del draft se nombran los dos
        """
        competicion = self._sin_capitan_a()

        with pytest.raises(TeamsNotAssignedError):
            competicion.fill_captain("A", DANI, team_player_ids=EQUIPO_A, has_teams=False)

    def test_tiene_que_ser_de_su_equipo(self):
        """
        Given: equipos repartidos
        When: se elige a alguien de fuera de ese equipo
        Then: se rechaza y no queda ninguno
        """
        competicion = self._sin_capitan_a()

        with pytest.raises(CaptainOnWrongTeamError):
            competicion.fill_captain("A", EVA, team_player_ids=EQUIPO_A, has_teams=True)

        assert competicion.team_a_captain_id is None

    def test_con_el_torneo_en_marcha_no(self):
        """
        Given: el torneo en marcha
        When: se intenta el cambio
        Then: se rechaza por el estado
        """
        competicion = self._sin_capitan_a()
        competicion.start()

        with pytest.raises(CompetitionStateError):
            competicion.fill_captain("A", DANI, team_player_ids=EQUIPO_A, has_teams=True)


class TestHandleWithdrawal:
    def test_si_se_va_el_capitan_asciende_el_subcapitan(self):
        """
        Given: Ana con Carla de subcapitana
        When: Ana se va
        Then: Carla asciende y su puesto queda libre
        """
        competicion = _repartida()
        competicion.name_vice_captain("A", CARLA, team_player_ids=EQUIPO_A, has_teams=True)

        assert competicion.handle_withdrawal(ANA) is True

        assert (competicion.team_a_captain_id, competicion.team_a_vice_captain_id) == (CARLA, None)

    def test_si_se_va_el_capitan_b_asciende_el_suyo(self):
        """
        Given: Bea con Eva de subcapitana
        When: Bea se va
        Then: Eva asciende y su puesto queda libre
        """
        competicion = _repartida()
        competicion.name_vice_captain("B", EVA, team_player_ids=EQUIPO_B, has_teams=True)

        competicion.handle_withdrawal(BEA)

        assert (competicion.team_b_captain_id, competicion.team_b_vice_captain_id) == (EVA, None)

    def test_sin_subcapitan_el_puesto_queda_libre(self):
        """
        Given: Bea sin subcapitana
        When: Bea se va
        Then: su puesto queda libre y Ana sigue
        """
        competicion = _repartida()

        competicion.handle_withdrawal(BEA)

        assert (competicion.team_a_captain_id, competicion.team_b_captain_id) == (ANA, None)

    def test_si_se_va_el_subcapitan_su_puesto_queda_libre(self):
        """
        Given: Carla de subcapitana del A
        When: Carla se va
        Then: su puesto queda libre y Ana sigue de capitana
        """
        competicion = _repartida()
        competicion.name_vice_captain("A", CARLA, team_player_ids=EQUIPO_A, has_teams=True)

        assert competicion.handle_withdrawal(CARLA) is True

        assert (competicion.team_a_captain_id, competicion.team_a_vice_captain_id) == (ANA, None)

    def test_si_se_va_otro_no_cambia_nada(self):
        """
        Given: capitanas nombradas
        When: se va Dani, que no es ni capitán ni subcapitán
        Then: nada cambia
        """
        competicion = _repartida()

        assert competicion.handle_withdrawal(DANI) is False

        assert (competicion.team_a_captain_id, competicion.team_b_captain_id) == (ANA, BEA)

    @pytest.mark.parametrize("estado", [CompetitionStatus.IN_PROGRESS, CompetitionStatus.COMPLETED])
    def test_con_el_torneo_en_marcha_no_se_toca_nada(self, estado):
        """Una baja ahí no puede borrar al capitán de un torneo que se está jugando."""
        competicion = _repartida(estado)

        assert competicion.handle_withdrawal(ANA) is False

        assert competicion.team_a_captain_id == ANA


class TestTeamsReassigned:
    def test_repartir_de_nuevo_deja_libres_los_subcapitanes(self):
        """Se eligen entre los del equipo, y el equipo ha cambiado."""
        competicion = _repartida()
        competicion.name_vice_captain("A", CARLA, team_player_ids=EQUIPO_A, has_teams=True)
        competicion.name_vice_captain("B", EVA, team_player_ids=EQUIPO_B, has_teams=True)

        competicion.teams_reassigned()

        assert competicion.team_a_vice_captain_id is None
        assert competicion.team_b_vice_captain_id is None
        assert (competicion.team_a_captain_id, competicion.team_b_captain_id) == (ANA, BEA)


class TestIsCaptainOf:
    def test_cada_capitan_lo_es_de_su_equipo(self):
        """
        Given: Ana capitana del A y Bea del B
        When: se pregunta por cada una en cada equipo
        Then: cada una lo es solo del suyo
        """
        competicion = _repartida()

        assert competicion.is_captain_of("A", ANA) is True
        assert competicion.is_captain_of("B", BEA) is True
        assert competicion.is_captain_of("A", BEA) is False
        assert competicion.is_captain_of("B", CARLA) is False

    def test_sin_capitan_nadie_lo_es(self):
        """
        Given: una competición sin capitanes
        When: se pregunta por Ana
        Then: no lo es de ninguno
        """
        assert _competicion(CompetitionStatus.CLOSED).is_captain_of("A", ANA) is False
