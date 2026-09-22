"""
La sala de draft (FE #653).

Diseñada con el dueño del producto el 22 sep: entran los dos capitanes, se
sortea delante de ellos quién empieza, el de turno tiene un minuto, y al elegir
salta al otro. Así hasta que no quede nadie por elegir.

Las tres decisiones del 22 sep, que son las que fijan esta tabla:

- **Si un capitán no entra, el organizador empieza igual** y la aplicación
  elige por él cada vez que se le agota el turno.
- **El sorteo lo lanza el organizador**, que es quien decide el resto.
- **Un turno agotado lo resuelve la aplicación** con el hándicap más bajo
  disponible, y pasa el turno. El draft nunca se queda parado.

El reloj es del SERVIDOR, como en la anotación (BE #305): dos móviles contando
su minuto se desincronizan y acaban eligiendo al mismo jugador dos veces.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.modules.competition.domain.entities.draft import (
    Draft,
    DraftNotRunningError,
    NotYourTurnError,
    PlayerAlreadyPickedError,
)
from src.modules.competition.domain.services.snake_draft_service import PlayerForDraft
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.draft_status import DraftStatus
from src.modules.user.domain.value_objects.user_id import UserId

ANA = UserId.generate()
BEA = UserId.generate()
CARLA = UserId.generate()
DANI = UserId.generate()
EVA = UserId.generate()
FEDE = UserId.generate()

# Los que se eligen: los capitanes no entran al draft, que nombrarlos ya los fijó
ELEGIBLES = [
    PlayerForDraft(user_id=CARLA, handicap=Decimal("5.0")),
    PlayerForDraft(user_id=DANI, handicap=Decimal("12.0")),
    PlayerForDraft(user_id=EVA, handicap=Decimal("18.0")),
    PlayerForDraft(user_id=FEDE, handicap=Decimal("24.0")),
]

AHORA = datetime(2030, 6, 1, 10, 0, 0, tzinfo=UTC).replace(tzinfo=None)


def _sala(**extra) -> Draft:
    return Draft.create(
        competition_id=CompetitionId.generate(),
        team_a_captain_id=ANA,
        team_b_captain_id=BEA,
        **extra,
    )


def _empezada(primer_turno: str = "A") -> Draft:
    sala = _sala()
    sala.start(first_pick=primer_turno, ahora=AHORA)
    return sala


class TestCrearLaSala:
    def test_nace_esperando_a_que_se_lance_el_sorteo(self):
        sala = _sala()

        assert sala.status == DraftStatus.PENDING
        assert sala.current_team is None
        assert sala.picks == ()

    def test_el_minuto_por_turno_es_el_de_siempre(self):
        """Un minuto, decidido el 20 sep. Se guarda para poder cambiarlo sin migrar."""
        assert _sala().seconds_per_turn == 60


class TestEmpezar:
    @pytest.mark.parametrize("equipo", ["A", "B"])
    def test_el_sorteo_fija_quien_empieza_y_arranca_su_turno(self, equipo):
        sala = _sala()

        sala.start(first_pick=equipo, ahora=AHORA)

        assert sala.status == DraftStatus.IN_PROGRESS
        assert sala.first_pick == equipo
        assert sala.current_team == equipo
        assert sala.turn_started_at == AHORA

    def test_no_se_empieza_dos_veces(self):
        """Volver a sortear a mitad cambiaría el orden con elecciones hechas."""
        sala = _empezada()

        with pytest.raises(DraftNotRunningError):
            sala.start(first_pick="B", ahora=AHORA)

    def test_un_equipo_que_no_existe(self):
        with pytest.raises(ValueError, match="equipo"):
            _sala().start(first_pick="C", ahora=AHORA)


class TestElegir:
    def test_el_elegido_va_al_equipo_del_turno_y_pasa_al_otro(self):
        sala = _empezada("A")

        sala.pick(CARLA, elegibles=ELEGIBLES, ahora=AHORA)

        assert [(p.user_id, p.team) for p in sala.picks] == [(CARLA, "A")]
        assert sala.current_team == "B"

    def test_y_el_turno_empieza_a_contar_de_nuevo(self):
        sala = _empezada("A")
        despues = AHORA + timedelta(seconds=30)

        sala.pick(CARLA, elegibles=ELEGIBLES, ahora=despues)

        assert sala.turn_started_at == despues

    def test_se_alternan_los_turnos(self):
        """Como lo describió: al elegir, salta al siguiente."""
        sala = _empezada("B")

        sala.pick(CARLA, elegibles=ELEGIBLES, ahora=AHORA)
        sala.pick(DANI, elegibles=ELEGIBLES, ahora=AHORA)

        assert [(p.user_id, p.team) for p in sala.picks] == [(CARLA, "B"), (DANI, "A")]
        assert sala.current_team == "B"

    def test_no_se_elige_dos_veces_al_mismo(self):
        sala = _empezada()
        sala.pick(CARLA, elegibles=ELEGIBLES, ahora=AHORA)

        with pytest.raises(PlayerAlreadyPickedError):
            sala.pick(CARLA, elegibles=ELEGIBLES, ahora=AHORA)

    def test_ni_a_alguien_que_no_esta_en_la_lista(self):
        """La lista la trae el caso de uso: son los inscritos que no capitanean."""
        sala = _empezada()

        with pytest.raises(PlayerAlreadyPickedError):
            sala.pick(ANA, elegibles=ELEGIBLES, ahora=AHORA)

    def test_sin_haber_empezado_no_se_elige(self):
        with pytest.raises(DraftNotRunningError):
            _sala().pick(CARLA, elegibles=ELEGIBLES, ahora=AHORA)

    def test_cuando_no_queda_nadie_la_sala_termina(self):
        sala = _empezada("A")

        for jugador in (CARLA, DANI, EVA, FEDE):
            sala.pick(jugador, elegibles=ELEGIBLES, ahora=AHORA)

        assert sala.status == DraftStatus.COMPLETED
        assert sala.current_team is None
        assert sala.turn_started_at is None

    def test_terminada_ya_no_se_elige(self):
        sala = _empezada()
        for jugador in (CARLA, DANI, EVA, FEDE):
            sala.pick(jugador, elegibles=ELEGIBLES, ahora=AHORA)

        with pytest.raises(DraftNotRunningError):
            sala.pick(CARLA, elegibles=ELEGIBLES, ahora=AHORA)


class TestDeQuienEsElTurno:
    def test_el_capitan_del_otro_equipo_no_elige_en_este_turno(self):
        sala = _empezada("A")

        with pytest.raises(NotYourTurnError):
            sala.check_turn(BEA)

    def test_el_capitan_de_turno_puede(self):
        _empezada("A").check_turn(ANA)

    def test_quien_no_capitanea_nada_no_elige(self):
        with pytest.raises(NotYourTurnError):
            _empezada("A").check_turn(CARLA)

    def test_sin_empezar_no_hay_turno_de_nadie(self):
        """«No es tu turno» mandaría al capitán a esperar uno que no existe."""
        with pytest.raises(DraftNotRunningError):
            _sala().check_turn(ANA)

    def test_terminada_tampoco(self):
        sala = _empezada("A")
        for jugador in (CARLA, DANI, EVA, FEDE):
            sala.pick(jugador, elegibles=ELEGIBLES, ahora=AHORA)

        with pytest.raises(DraftNotRunningError):
            sala.check_turn(ANA)


class TestElRelojDelServidor:
    def test_el_turno_expira_al_minuto(self):
        sala = _empezada()

        assert sala.turn_expired(AHORA + timedelta(seconds=59)) is False
        assert sala.turn_expired(AHORA + timedelta(seconds=61)) is True

    def test_sin_empezar_no_expira_nada(self):
        assert _sala().turn_expired(AHORA + timedelta(hours=5)) is False

    def test_el_minuto_se_acaba_un_minuto_despues_de_empezar(self):
        """El turno siguiente empieza AHÍ, no cuando alguien mire la sala."""
        assert _empezada().turn_deadline == AHORA + timedelta(seconds=60)

    def test_sin_turno_no_hay_vencimiento(self):
        assert _sala().turn_deadline is None

    def test_quien_elige_la_app_es_el_handicap_mas_bajo(self):
        """Decidido el 20 sep: el draft nunca se queda parado."""
        sala = _empezada("A")

        elegido = sala.pick_for_expired_turn(elegibles=ELEGIBLES, ahora=AHORA)

        assert elegido == CARLA
        assert [(p.user_id, p.team, p.automatic) for p in sala.picks] == [(CARLA, "A", True)]

    def test_y_sigue_siendo_el_mas_bajo_de_los_que_quedan(self):
        sala = _empezada("A")
        sala.pick(CARLA, elegibles=ELEGIBLES, ahora=AHORA)

        elegido = sala.pick_for_expired_turn(elegibles=ELEGIBLES, ahora=AHORA)

        assert elegido == DANI

    def test_una_eleccion_a_mano_no_se_marca_como_automatica(self):
        sala = _empezada("A")

        sala.pick(DANI, elegibles=ELEGIBLES, ahora=AHORA)

        assert sala.picks[0].automatic is False


class TestLosEquiposQueSalen:
    def test_cada_capitan_encabeza_el_suyo_y_luego_sus_elegidos(self):
        sala = _empezada("A")
        for jugador in (CARLA, DANI, EVA, FEDE):
            sala.pick(jugador, elegibles=ELEGIBLES, ahora=AHORA)

        equipo_a, equipo_b = sala.teams()

        assert equipo_a == [ANA, CARLA, EVA]
        assert equipo_b == [BEA, DANI, FEDE]

    def test_a_medias_tambien_se_pueden_mirar(self):
        """La ficha enseña los equipos llenándose en directo."""
        sala = _empezada("B")
        sala.pick(CARLA, elegibles=ELEGIBLES, ahora=AHORA)

        assert sala.teams() == ([ANA], [BEA, CARLA])
