"""
El sobre de un capitán (FE #655).

Así es como lo hace la Ryder de verdad, y por eso se hace así aquí: cada
capitán entrega una **lista ordenada** de los suyos —jugadores en individuales,
parejas en los formatos de dos— sin ver la del otro, y los enfrentamientos
salen de cruzar las dos listas **por posición**: el primero contra el primero.
El azar está en no saber qué hizo el rival.

Dos decisiones del 20 sep que fijan esta tabla:

- **Juegan todos.** Aquí no se descansa: si sois doce, salen seis parejas y no
  hay a quién sentar. Un sobre al que le falte alguien del equipo no vale.
- **Lo que falte al vencer el plazo lo rellena la aplicación**, y lo que hace
  la aplicación se puede seguir editando.
"""

from datetime import datetime

import pytest

from src.modules.competition.domain.entities.envelope import (
    Envelope,
    EnvelopeAlreadyRevealedError,
    PlayerNotInTeamError,
    TeamNotFullyEnteredError,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId

ANA, BEA, CARLA, DANI = (UserId.generate() for _ in range(4))
EQUIPO = [ANA, BEA, CARLA, DANI]
AJENO = UserId.generate()
AHORA = datetime(2030, 6, 1, 10, 0, 0)


def _sobre(**extra) -> Envelope:
    argumentos = {
        "competition_id": CompetitionId.generate(),
        "round_id": RoundId.generate(),
        "team": "A",
        "match_format": MatchFormat.SINGLES,
    }
    return Envelope.create(**{**argumentos, **extra})


class TestEntregarElSobre:
    def test_en_individuales_es_el_orden_de_los_jugadores(self):
        sobre = _sobre()

        sobre.submit([[CARLA], [ANA], [DANI], [BEA]], equipo=EQUIPO, por=ANA, ahora=AHORA)

        assert sobre.entries == ((CARLA,), (ANA,), (DANI,), (BEA,))
        assert sobre.submitted_at == AHORA
        assert sobre.submitted_by == ANA
        assert sobre.automatic is False

    def test_en_parejas_es_el_orden_de_las_parejas(self):
        sobre = _sobre(match_format=MatchFormat.FOURBALL)

        sobre.submit([[CARLA, ANA], [DANI, BEA]], equipo=EQUIPO, por=ANA, ahora=AHORA)

        assert sobre.entries == ((CARLA, ANA), (DANI, BEA))

    def test_una_pareja_coja_no_vale(self):
        """En fourball se juega dos contra dos: una fila de uno no es una pareja."""
        sobre = _sobre(match_format=MatchFormat.FOURBALL)

        with pytest.raises(ValueError, match="(?i)pareja|dos"):
            sobre.submit([[CARLA, ANA], [DANI]], equipo=EQUIPO, por=ANA, ahora=AHORA)

    def test_ni_dos_jugadores_en_un_individual(self):
        sobre = _sobre()

        with pytest.raises(ValueError, match="(?i)individual|uno"):
            sobre.submit([[CARLA, ANA], [DANI], [BEA]], equipo=EQUIPO, por=ANA, ahora=AHORA)

    def test_no_se_puede_meter_a_alguien_del_otro_equipo(self):
        sobre = _sobre()

        with pytest.raises(PlayerNotInTeamError):
            sobre.submit([[AJENO], [ANA], [DANI], [BEA]], equipo=EQUIPO, por=ANA, ahora=AHORA)

    def test_ni_repetir_a_uno_para_que_juegue_dos_veces(self):
        sobre = _sobre()

        with pytest.raises(ValueError, match="(?i)repetid|dos veces"):
            sobre.submit([[ANA], [ANA], [DANI], [BEA]], equipo=EQUIPO, por=ANA, ahora=AHORA)

    def test_tienen_que_estar_todos(self):
        """Aquí no se descansa: si sois doce, salen los doce (decidido el 20 sep)."""
        sobre = _sobre()

        with pytest.raises(TeamNotFullyEnteredError):
            sobre.submit([[CARLA], [ANA], [DANI]], equipo=EQUIPO, por=ANA, ahora=AHORA)

    def test_se_puede_cambiar_de_idea_hasta_que_se_abre(self):
        sobre = _sobre()
        sobre.submit([[CARLA], [ANA], [DANI], [BEA]], equipo=EQUIPO, por=ANA, ahora=AHORA)

        sobre.submit([[ANA], [BEA], [CARLA], [DANI]], equipo=EQUIPO, por=ANA, ahora=AHORA)

        assert sobre.entries == ((ANA,), (BEA,), (CARLA,), (DANI,))

    def test_abierto_ya_no_se_toca(self):
        """Cambiarlo después es rehacer el sorteo a escondidas."""
        sobre = _sobre()
        sobre.submit([[CARLA], [ANA], [DANI], [BEA]], equipo=EQUIPO, por=ANA, ahora=AHORA)
        sobre.reveal()

        with pytest.raises(EnvelopeAlreadyRevealedError):
            sobre.submit([[ANA], [BEA], [CARLA], [DANI]], equipo=EQUIPO, por=ANA, ahora=AHORA)


class TestElQueRellenaLaAplicacion:
    def test_ordena_por_handicap_de_menor_a_mayor(self):
        """El mismo criterio que usa para todo lo demás: el que mejor juega, primero."""
        sobre = _sobre()

        sobre.fill([(DANI, 24), (ANA, 5), (BEA, 12), (CARLA, 18)], ahora=AHORA)

        assert sobre.entries == ((ANA,), (BEA,), (CARLA,), (DANI,))
        assert sobre.automatic is True

    def test_en_parejas_junta_al_mejor_con_el_peor(self):
        """Como el reparto automático: parejas equilibradas, no una fuerte y otra floja."""
        sobre = _sobre(match_format=MatchFormat.FOURBALL)

        sobre.fill([(DANI, 24), (ANA, 5), (BEA, 12), (CARLA, 18)], ahora=AHORA)

        assert sobre.entries == ((ANA, DANI), (BEA, CARLA))

    def test_no_pisa_el_que_entrego_el_capitan(self):
        """El que llegó a tiempo no se queda sin su lista por el que se olvidó."""
        sobre = _sobre()
        sobre.submit([[CARLA], [ANA], [DANI], [BEA]], equipo=EQUIPO, por=ANA, ahora=AHORA)

        sobre.fill([(DANI, 24), (ANA, 5), (BEA, 12), (CARLA, 18)], ahora=AHORA)

        assert sobre.entries == ((CARLA,), (ANA,), (DANI,), (BEA,))
        assert sobre.automatic is False

    def test_lo_que_rellena_la_aplicacion_se_puede_editar(self):
        """Decidido el 20 sep: lo automático no queda grabado en piedra."""
        sobre = _sobre()
        sobre.fill([(DANI, 24), (ANA, 5), (BEA, 12), (CARLA, 18)], ahora=AHORA)

        sobre.submit([[BEA], [ANA], [DANI], [CARLA]], equipo=EQUIPO, por=ANA, ahora=AHORA)

        assert sobre.entries == ((BEA,), (ANA,), (DANI,), (CARLA,))
        assert sobre.automatic is False


class TestQueVeQuien:
    def test_sin_abrir_no_se_ensena_lo_que_hay_dentro(self):
        """Ver la lista del rival antes de tiempo es el juego entero."""
        sobre = _sobre()
        sobre.submit([[CARLA], [ANA], [DANI], [BEA]], equipo=EQUIPO, por=ANA, ahora=AHORA)

        assert sobre.is_sealed() is True
        assert sobre.is_submitted() is True

    def test_abierto_deja_de_estarlo(self):
        sobre = _sobre()
        sobre.submit([[CARLA], [ANA], [DANI], [BEA]], equipo=EQUIPO, por=ANA, ahora=AHORA)

        sobre.reveal()

        assert sobre.is_sealed() is False

    def test_uno_vacio_ni_esta_entregado_ni_se_abre(self):
        sobre = _sobre()

        assert sobre.is_submitted() is False
        with pytest.raises(ValueError, match="(?i)vac"):
            sobre.reveal()


class TestCruzarLosDosSobres:
    def test_los_enfrentamientos_salen_por_posicion(self):
        """El primero contra el primero: así lo hace la Ryder de verdad."""
        uno, dos, tres, cuatro = (UserId.generate() for _ in range(4))
        sobre_a = _sobre()
        sobre_a.submit([[CARLA], [ANA], [DANI], [BEA]], equipo=EQUIPO, por=ANA, ahora=AHORA)
        sobre_b = Envelope.create(
            competition_id=sobre_a.competition_id,
            round_id=sobre_a.round_id,
            team="B",
            match_format=MatchFormat.SINGLES,
        )
        rival = [uno, dos, tres, cuatro]
        sobre_b.submit([[dos], [cuatro], [uno], [tres]], equipo=rival, por=uno, ahora=AHORA)

        enfrentamientos = Envelope.pair_up(sobre_a, sobre_b)

        assert enfrentamientos == [
            ((CARLA,), (dos,)),
            ((ANA,), (cuatro,)),
            ((DANI,), (uno,)),
            ((BEA,), (tres,)),
        ]

    def test_con_equipos_desiguales_juegan_los_que_se_pueden_emparejar(self):
        """El draft admite uno de diferencia: el que sobra no tiene rival."""
        uno, dos, tres = (UserId.generate() for _ in range(3))
        sobre_a = _sobre()
        sobre_a.submit([[CARLA], [ANA], [DANI], [BEA]], equipo=EQUIPO, por=ANA, ahora=AHORA)
        sobre_b = Envelope.create(
            competition_id=sobre_a.competition_id,
            round_id=sobre_a.round_id,
            team="B",
            match_format=MatchFormat.SINGLES,
        )
        sobre_b.submit([[uno], [dos], [tres]], equipo=[uno, dos, tres], por=uno, ahora=AHORA)

        enfrentamientos = Envelope.pair_up(sobre_a, sobre_b)

        assert len(enfrentamientos) == 3

    def test_no_se_cruzan_sobres_de_rondas_distintas(self):
        """Serían los enfrentamientos de otra sesión, y nadie lo notaría."""
        sobre_a = _sobre()
        sobre_a.submit([[CARLA], [ANA], [DANI], [BEA]], equipo=EQUIPO, por=ANA, ahora=AHORA)
        otro = _sobre(team="B")
        otro.submit([[ANA], [BEA], [CARLA], [DANI]], equipo=EQUIPO, por=BEA, ahora=AHORA)

        with pytest.raises(ValueError, match="(?i)ronda"):
            Envelope.pair_up(sobre_a, otro)
